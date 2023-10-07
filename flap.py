#!/usr/bin/env python3

import os
import sys
import json
import os.path
import time
import subprocess
import shutil
from datetime import datetime
import argparse
import random
from collections import namedtuple
import string

WIDTH = 15
HEIGHT = 20
GROUND_HEIGHT = 2
PIPE_WIDTH = 3
PLAYER_X = 3
TARGET_FPS = 4
TARGET_FRAMETIME = 1.0 / TARGET_FPS
MAX_FRAME = 100
SCORE_LINE = -2

BUFFER_1 = "./buf1"
BUFFER_2 = "./buf2"
STATE_FILE = "./state.json"

BLUE   = "🟦"
GREEN  = "🟩"
WHITE  = "⬜️"
# ig proposed using folders for "flapping" which is a *great* idea but doesn't quite work
# out in practice :/. Maybe revisit.
WING1  = "📂"
WING2  = "📁"
BROWN =  "🟫"
YELLOW = "🟨"
ORANGE = "🟧"
X      = "❌"
RED    = "🟥"
EYES   = "👀"
COOL   = "🆒"
PLANE  = "✈️"
STARTING_AD_SPACING = len("                                                                  ")
# You might be inclined to put these in a string and index into that string but
# indexing into unicode strings is *hard*
NUMBERS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
NUMBERS = {str(i):NUMBERS[i] for i in range(len(NUMBERS))}
LETTERS = ["𝑨", "𝑩", "𝑪", "𝑫", "𝑬", "𝑭", "𝑮", "𝑯", "𝑰", "𝑱", "𝑲", "𝑳", "𝑴", "𝑵", "𝑶", "𝑷", "𝑸", "𝑹", "𝑺", "𝑻", "𝑼", "𝑽", "𝑾", "𝑿", "𝒀", "𝒁"]
LETTERS = dict(zip(string.ascii_lowercase, LETTERS))
for c in (" ", "|", ".", "1", "0", ","):
    LETTERS[c] = c
def letterify(s): return "".join(LETTERS[c] for c in s)
POINT_RIGHT = "👉"
POINT_LEFT  = "👈"
GEM = "💎"
TROPHY = "🏆"
GRID = []
_AD_TEXTS = [ ("you are the 1,000,000th visitor to this finder window", ), 
      ("hot", "UU🌶️", "local singles", "UU🦹", "in your area are waiting to chat"),
      ("made by eieio | check out eieio.games for more"),
      ("UU🦧", "bonzo buddy toolbar free download", "UU🦍"),
     ]
AD_TEXTS = []
for ad in _AD_TEXTS:
    AD_TEXTS.append([text if text.startswith("UU") else letterify(text) for text in ad])
AD_STARTING_PADDING_SPACES = 70

PipePair = namedtuple("PipePair", ["x", "midpoint", "space_between_top_and_bottom"])
def generate_random_pipe(x):
    highest_midpoint = 5
    lowest_midpoint = 12
    midpoint = random.randint(5, 12)

    min_space = 5
    max_space = 8
    space_between_top_and_bottom = random.randint(min_space, max_space)
    return PipePair(x=x,
                    midpoint=midpoint,
                    space_between_top_and_bottom=space_between_top_and_bottom)

def to_top_and_bottom(pipe):
    half_of_space = pipe.space_between_top_and_bottom // 2
    top_height = pipe.midpoint - half_of_space - pipe.space_between_top_and_bottom % 2
    bottom_height = HEIGHT - GROUND_HEIGHT - pipe.midpoint - half_of_space

    return (pipe.x, top_height), (pipe.x, bottom_height)

def write_state(state):
    with open(STATE_FILE, "w") as f:
        f.write(json.dumps(state, default=str))

def read_state():
    with open(STATE_FILE, "r") as f:
        d = json.loads(f.read().strip())
        if d["tick_start_time"]:
            d["tick_start_time"] = datetime.fromisoformat(d["tick_start_time"])
        d["pipes"] = [PipePair(*pipe) for pipe in d["pipes"]]
        return d

def get_initial_state():
    first_two_pairs = [PipePair(12, 8, 8), PipePair(20, 9, 9)]
    state = {}
    if os.path.exists(STATE_FILE):
        state = read_state()

    initial = {"frame": 0, 
             "write_to_buf1": True,
             "player_y": 5,
             "fall_speed": -3,
             "tick_start_time": None,
             "flapped_on_prior_frame": False,
             "state": "waiting",
             "pipes": first_two_pairs,
             "score": 8,
             }

    for k, v in initial.items(): 
        state[k] = v

    if "high_score" not in state: 
        state["high_score"] = 0

    return state

def get_top_and_bottom(state):
    return zip(*[to_top_and_bottom(p) for p in state["pipes"]])

def displayed_buffer(state):
    if state["write_to_buf1"]: return BUFFER_2
    return BUFFER_1

def buffer_to_write_to(state):
    if state["write_to_buf1"]: return BUFFER_1
    return BUFFER_2

def initialize_buffers():
    cwd = os.getcwd()

    for dir_ in (BUFFER_1, BUFFER_2):
        if not os.path.exists(dir_): os.mkdir(dir_)

        for file in os.listdir(dir_):
            if file.startswith("."): continue
            os.remove(f"{cwd}/{dir_}/{file}")

        os.symlink(f"{cwd}/{dir_}", f"{dir_}/{COOL}")

        for i in range(HEIGHT):
            os.symlink(f"{cwd}/{dir_}", f"{dir_}/{i}")

        os.symlink(f"{cwd}/{dir_}", f"{dir_}/{POINT_RIGHT}")

def all_pipe_locations(x, frame, height, is_top):
    x = x - frame
    for pipe_x in range(x, x + PIPE_WIDTH):
        if pipe_x < 0 or pipe_x >= WIDTH: continue
        for pipe_y in range(height):
            if is_top: # no remapping on top
                pipe_y = pipe_y
            else:
                # e.g. 0 = 19, the last element, if HEIGHT = 20
                pipe_y = HEIGHT - pipe_y - 1 
                # last few elements don't contain a pipe
                pipe_y -= GROUND_HEIGHT
            yield (pipe_x, pipe_y)

def all_player_coords(state):
    player_y = state["player_y"]
    for x,y,c in ((0, 0, EYES), (-1, 0, WHITE), (0, 1, ORANGE), (-1, 1,YELLOW)):
        yield (PLAYER_X + x, player_y + y, c)

def initialize_grid():
    for h in range(HEIGHT):
        if h + GROUND_HEIGHT >= HEIGHT: color = BROWN
        else: color = BLUE
        GRID.append([color for _ in range(WIDTH)])
    
def add_pipes_to_grid(state):
    frame = state["frame"]
    top, bottom = get_top_and_bottom(state)
    for (locations, is_top) in [(top, True), (bottom, False)]:
        for (x, height) in locations:
            for (pipe_x, pipe_y) in all_pipe_locations(x, frame, height, is_top):
                second_to_last = False
                if is_top: 
                    second_to_last = pipe_y + 2 == height
                else: 
                    second_to_last_height = HEIGHT - GROUND_HEIGHT - 1
                    second_to_last_height = second_to_last_height - height + 2
                    second_to_last = (pipe_y == second_to_last_height)
                color = WHITE if second_to_last else GREEN
                GRID[pipe_y][pipe_x] = color

def add_player_to_grid(state, collisions):
    dead = state["state"] in {"dying", "dead"}
    # I tried putting eyes in the bottom right to emphasize that we're falling
    ## it feels like we should be able to do this but it ends up looking weird,
    # I think it's because the orientation of the eyes emoji doesn't change?
    for (x, y, c) in all_player_coords(state):
        if y < HEIGHT:
            if (x, y) in collisions:
                GRID[y][x] = X
            elif dead and c != EYES:
                GRID[y][x] = RED
            else:
                GRID[y][x] = c

def add_score_to_grid(state):
    def add_aux(line, score, icon):
        emojis = "".join(NUMBERS[s] for s in str(score))
        # unicode chars have a length greater than one!
        emoji_len = len(str(score)) + 1
        GRID[line][-2] = icon
        GRID[line][-emoji_len-2:-3] = emojis

    add_aux(SCORE_LINE, state["score"], GEM)
    add_aux(SCORE_LINE+1, state["high_score"], TROPHY)


class READ_STATE:
    READ_SOME = 1
    READ_ALL__BEGIN_SKIPPING = 2
    SKIPPED_ALL = 3

# We do all of this weirdness just because I couldn't think of an easy way to handle
# indexing into a unicode string and i wrote this code without internet. I'm sure
# there's a "correct" way to handle all of this.
#
# It might be nice to instead just generate a huge random string at init time and
# then index into it. Oh well.
def read_n_ad_chars(ad, skip, take):
    ad = list(ad)
    # returns: text, count, took all
    def read_n(subloc, n):
        text = ad[subloc]
        if text.startswith("UU"):
            return (text[2:], 2, True)
        else:
            count = min(n, len(text))
            took_all = len(text) <= n
            return (text[:n], count, took_all)

    def skip_n(subloc, n):
        if n <= 0: return False, subloc
        if subloc >= len(ad): return True, subloc

        _, count, took_all = read_n(subloc, n)
        if took_all: return skip_n(subloc + 1, n - count)
        else:
            ad[subloc] = ad[subloc][n:]
            return False, subloc

    def take_n(subloc, n, acc):
        if n <= 0: return False, acc
        if subloc >= len(ad): return True, acc

        text, count, took_all = read_n(subloc, n)
        if took_all: return take_n(subloc + 1, n - count, acc + text)
        else: return False, acc + text

    skipped_all, subloc = skip_n(0, skip)
    if skipped_all: return (READ_STATE.SKIPPED_ALL, "")

    took_all, text = take_n(subloc, take, "")
    if took_all: return (READ_STATE.READ_ALL__BEGIN_SKIPPING, text)
    else: return (READ_STATE.READ_SOME, text)

    #subloc = 0
    #while skip > 0:
        #if subloc >= len(ad):
            ## god damn the lack of variants in this cursed language
            #return (READ_STATE.SKIPPED_ALL, "")
        #_, count, took_all = read_n(subloc, skip)
        #if took_all:
            #skip -= count
            #subloc += 1
        #else:
            #skip = 0
            #ad[subloc] = ad[subloc][count:]

    #s = ""
    ##subloc = 0
    #while take > 0:
        #if subloc >= len(ad):
            #return (READ_STATE.READ_ALL__BEGIN_SKIPPING, s)

        #text, count, took_all = read_n(subloc, take)
        #if took_all:
            #take -= count
            #s += text
            #subloc += 1
        #else:
            #take = 0
            #s += text

    #return (READ_STATE.READ_SOME, s)

def add_banner_to_grid(state):
    ad_start_frame = 2
    ad_index = 3
    message = AD_TEXTS[ad_index]
    frames_passed = state["frame"] - ad_start_frame
    frames_passed *= 2
    padding_to_remove = max(frames_passed, 0)
    characters_to_show = int(padding_to_remove / 2.0)

    result, ad_text = read_n_ad_chars(message, 0, characters_to_show)

    padding = " " * (STARTING_AD_SPACING - padding_to_remove)
    text = f"{padding}{PLANE} {ad_text}"

    GRID.insert(0, f"{COOL}{text}")

def add_directive_to_grid(directive):
    spaces, letters = directive
    letters = letterify(letters)
    spaces = " " * spaces
    text = f"{spaces}{POINT_RIGHT} {letters}"
    GRID.append(text)

def file_sort_key(filename):
    # Directive, goes at the bottom
    if POINT_RIGHT in filename: return HEIGHT*2
    # Banner, goes at the top
    if COOL in filename: 
        return -1
    return int(filename.split(" ")[-1])

def write_grid(state):
    target_dir = buffer_to_write_to(state)
    files = sorted(
            (file for file in os.listdir(target_dir) if not file.startswith(".")),
            key=file_sort_key)

    for idx, (file, gridline) in enumerate(zip(files, GRID)):
        file = os.path.join(target_dir, file)
        gridline = "".join(gridline)
        suffix = idx
        if POINT_RIGHT in gridline:
            suffix = f" {POINT_LEFT}"
        if COOL in gridline:
            suffix = ""
        gridline = os.path.join(target_dir, f"{gridline} {suffix}")

        # We touch the file to ensure its mtime gets updated. This matters
        # because we assume finder is sorting by "Date Modified"
        # sorting by name also works but finder sometimes seems to apply the
        # sort only *after* displaying the files.
        if file != gridline: os.rename(file, gridline)
        else: subprocess.check_output(["touch", file])
    
    # This is how applescript knows which directory to flip to
    print(target_dir.split("/")[-1])
    state["write_to_buf1"] = not state["write_to_buf1"]

def check_for_collision(state):
    player_coords = set((x, y) for (x, y, _c) in all_player_coords(state))

    frame = state["frame"]
    collisions = set()
    top, bottom = get_top_and_bottom(state)
    for (locations, is_top) in [(top, True), (bottom, False)]:
        for (x, height) in locations:
            for (pipe_x, pipe_y) in all_pipe_locations(x, frame, height, is_top):
                if (pipe_x, pipe_y) in player_coords:
                    collisions.add((pipe_x, pipe_y))

    for (x, y) in player_coords:
        if y >= HEIGHT - GROUND_HEIGHT:
            collisions.add((x, y))
    return collisions

def get_last_opened(state):
    buffer = displayed_buffer(state)
    command = f"mdls -attr kMDItemLastUsedDate {buffer}"
    return subprocess.check_output(command.split()).strip().decode("utf-8")

def await_command(args):
    state = read_state()
    current_last_opened = get_last_opened(state)
    while True:
        last_opened = get_last_opened(state)
        if last_opened != current_last_opened: break
        time.sleep(0.25)

def append_to_log(message):
    with open("log", "a") as f:
        f.write(f"{message}\n")

def sleep_command(args):
    state = read_state()
    start_of_frame = state["tick_start_time"]

    if start_of_frame is not None:
        now = datetime.now()
        time_spent_on_frame = (now - start_of_frame).total_seconds()
        diff = TARGET_FRAMETIME - time_spent_on_frame

        append_to_log(f"FRAMETIME: {time_spent_on_frame}")

        if diff > 0:
            time.sleep(diff)

    state["tick_start_time"] = datetime.now()

    if state["state"] == "dying" or state["state"] == "dead":
        append_to_log(f"DYING/DEAD: {state}")

    # This is read back by applescript and determines when applescript
    # stops looping. The "stop looping" condition is just whether
    # this string is "continue" or not - we use different values
    # here just for some simple debugging.
    if state["frame"] >= MAX_FRAME:
        print("max-frame")
    elif state["state"] == "dead":
        print("dead")
    else:                           
        if state["state"] == "ticking":
            state["frame"] += 1
        print("continue")

    write_state(state)

def prune_and_maybe_add_pipe(state):
    new_pipes = []
    for pipe in state["pipes"]:
        if pipe.x + PIPE_WIDTH - state["frame"] < 0: 
            append_to_log(f"PRUNE %{pipe}")
            continue
        else: new_pipes.append(pipe)

    # This is a pretty boring / simple heuristic and it might
    # be nice to add a little randomness here
    if len(new_pipes) < len(state["pipes"]):
        x = WIDTH + 1 + state["frame"]
        pipe = generate_random_pipe(x)
        append_to_log(f"GEN NEW PIPE {pipe}")
        new_pipes.append(pipe)
    state["pipes"] = new_pipes

def maybe_increment_score(state):
    if state["pipes"][0].x == PLAYER_X + state["frame"]:
        state["score"] += 1

    state["high_score"] = max(state["score"], state["high_score"])

def handle_tick_running(state, count):
    prune_and_maybe_add_pipe(state)
    flapped = count > 0
    fall_speed = state["fall_speed"]
    player_y = state["player_y"]
    
    if flapped:
        fall_speed = -2
        movement = 2 if state["flapped_on_prior_frame"] else 1
        player_y = max(player_y - movement, 0)
    else:
        fall_speed = min(2, fall_speed + 1)
        player_y = min(max(player_y + fall_speed,0), HEIGHT - 1)

    state["flapped_on_prior_frame"] = flapped
    state["fall_speed"] = fall_speed
    state["player_y"] = player_y
    collisions = check_for_collision(state)

    if collisions:
        state["state"] = "dying"
    else:
        maybe_increment_score(state)

    return collisions

def handle_tick_dying(state):
    directive = 20, "game over"
    player_y = state["player_y"] 
    if player_y >= HEIGHT - 1 - GROUND_HEIGHT:
        state["state"] = "dead"
        directive = 6, "double click to restart"
    player_y = min(player_y + 2, HEIGHT - 1 - GROUND_HEIGHT)
    state["player_y"] = player_y
    return directive

def create_and_write_grid(state, directive, collisions):
    initialize_grid()
    add_pipes_to_grid(state)
    add_player_to_grid(state, collisions)
    add_score_to_grid(state)
    if directive: 
        add_directive_to_grid(directive)
    add_banner_to_grid(state)
    write_grid(state)

def tick_command(args):
    state = read_state()

    match state["state"]:
        case "waiting":
            state["state"] = "ticking"
            collisions = handle_tick_running(state, args.selection_count)
            directive = 17, "click to flap"
        case "ticking":
            collisions = handle_tick_running(state, args.selection_count)
            directive = 17, "click to flap"
        case "dying" | "dead":
            directive = handle_tick_dying(state)
            collisions = set()

    create_and_write_grid(state, directive, collisions)
    write_state(state)

def initialize_command(args):
    state = get_initial_state()
    initialize_buffers()
    if os.path.exists("log"):
        os.remove("log")
    create_and_write_grid(state, (8, "double click to start"), set())
    write_state(state)

def first_time_setup_command(args):
    my_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    template = f"{my_dir}/template.applescript" 
    target   = f"{my_dir}/flappy-dird.applescript"
    if os.path.exists(target):
        os.remove(target)
    shutil.copy(template, target)
    subprocess.check_output(["sed", "-i", "", f"s#@CWD#{my_dir}#g", target])

def main():
    parser = argparse.ArgumentParser(description="Run flappy dird")

    subparsers = parser.add_subparsers(title="commands", dest="command")

    initialize_parser = subparsers.add_parser("init", help="Initialize flappy dird")
    initialize_parser.set_defaults(func=initialize_command)

    tick_parser = subparsers.add_parser("tick", help="Run a game tick")
    tick_parser.add_argument("selection_count", type=int, help="Number of files selected")
    tick_parser.set_defaults(func=tick_command)

    await_parser = subparsers.add_parser("await", help="Await game start")
    await_parser.set_defaults(func=await_command)

    sleep_parser = subparsers.add_parser("sleep", help="Sleep between ticks")
    sleep_parser.set_defaults(func=sleep_command)

    first_time_setup = subparsers.add_parser("first-time-setup", help="One-time setup to prepare flappy dird")
    first_time_setup.set_defaults(func=first_time_setup_command)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
