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

WIDTH = 15
HEIGHT = 20
GROUND_HEIGHT = 2
PIPE_WIDTH = 3
PLAYER_X = 3
TARGET_FPS = 4
TARGET_FRAMETIME = 1.0 / TARGET_FPS
MAX_FRAME = 40

BUFFER_1 = "./buf1"
BUFFER_2 = "./buf2"
STATE_FILE = "./state.json"

BLUE   = "🟦"
GREEN  = "🟩"
WHITE  = "⬜️"
WING1  = "📂"
WING2  = "📁"
BROWN =  "🟫"
YELLOW = "🟨"
ORANGE = "🟧"
X      = "❌"
RED    = "🟥"
EYES   = "👀"

BOTTOM = [(10, 4), (24, 4), (38, 6)]
TOP = [(16, 4), (24, 4), (30, 6)]

def write_state(state):
    with open(STATE_FILE, "w") as f:
        f.write(json.dumps(state, default=str))

def read_state():
    with open(STATE_FILE, "r") as f:
        d = json.loads(f.read().strip())
        if d["tick_start_time"]:
            d["tick_start_time"] = datetime.fromisoformat(d["tick_start_time"])
        return d

def get_initial_state():
    state = {"frame": 0, 
             "write_to_buf1": True,
             "player_y": 5,
             "fall_speed": 0,
             "tick_start_time": None,
             "flapped_on_prior_frame": False,
             "state": "waiting"
             }
    return state

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

        for i in range(HEIGHT):
            os.symlink(f"{cwd}/{dir_}", f"{dir_}/{i}")

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
    
def add_pipes_to_grid(grid, frame):
    for (is_top, locations) in ((True, TOP), (False, BOTTOM)):
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
                grid[pipe_y][pipe_x] = color

def add_player_to_grid(grid, state, collisions):
    dead = state["state"] in {"dying", "dead"}
    # I tried putting eyes in the bottom right to emphasize that we're falling
    ## it feels like we should be able to do this but it ends up looking weird,
    # I think it's because the orientation of the eyes emoji doesn't change?
    for (x, y, c) in all_player_coords(state):
        if y < HEIGHT:
            if (x, y) in collisions:
                grid[y][x] = X
            elif dead and c != EYES:
                grid[y][x] = RED
            else:
                grid[y][x] = c

def draw_grid(state, grid):
    target_dir = buffer_to_write_to(state)
    files = sorted(
            (file for file in os.listdir(target_dir) if not file.startswith(".")),
            key=lambda x:int(x.split(" ")[-1]))

    for idx, (file, grid) in enumerate(zip(files, grid)):
        file = os.path.join(target_dir, file)
        grid = "".join(grid)
        grid = os.path.join(target_dir, f"{grid} {idx}")

        # We touch the file to ensure its mtime gets updated. This matters
        # because we assume finder is sorting by "Date Modified"
        # sorting by name also works but finder sometimes seems to apply the
        # sort only *after* displaying the files.
        if file != grid: os.rename(file, grid)
        else: subprocess.check_output(["touch", file])
    
    # This is how applescript knows which directory to flip to
    print(target_dir.split("/")[-1])
    state["write_to_buf1"] = not state["write_to_buf1"]

def check_for_collision(state):
    player_coords = set((x, y) for (x, y, _c) in all_player_coords(state))

    frame = state["frame"]
    collisions = set()
    for (is_top, locations) in ((True, TOP), (False, BOTTOM)):
        for (x, height) in locations:
            for (pipe_x, pipe_y) in all_pipe_locations(x, frame, height, is_top):
                if (pipe_x, pipe_y) in player_coords:
                    collisions.add((pipe_x, pipe_y))
    return collisions

def create_and_draw_grid(state, collisions):
    grid = []
    for h in range(HEIGHT):
        if h + GROUND_HEIGHT >= HEIGHT: color = BROWN
        else: color = BLUE
        grid.append([color for _ in range(WIDTH)])
    add_pipes_to_grid(grid, state["frame"])
    add_player_to_grid(grid, state, collisions)
    draw_grid(state, grid)

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
        append_to_log(f"{state}")

    # This is read back by applescript and determines when applescript
    # stops looping. The "stop looping" condition is just whether
    # this string is "continue" or not - we use different values
    # here just for some simple debugging.
    if state["frame"] >= MAX_FRAME: print("max-frame")
    elif state["state"] == "dead":  print("dead")
    else:                           print("continue")

    write_state(state)

def handle_tick_running(state, count):
    flapped = count > 0
    fall_speed = state["fall_speed"]
    player_y = state["player_y"]
    
    if flapped:
        fall_speed = -2
        movement = 2 if state["flapped_on_prior_frame"] else 1
        player_y = max(player_y - movement, 0)
    else:
        fall_speed = min(2, fall_speed + 1)
        player_y = min(player_y + fall_speed, HEIGHT - 1)

    state["flapped_on_prior_frame"] = flapped
    state["fall_speed"] = fall_speed
    state["player_y"] = player_y
    collisions = check_for_collision(state)

    create_and_draw_grid(state, collisions)
    if collisions:
        state["state"] = "dying"
    state["frame"] += 1
    write_state(state)

def handle_tick_dying(state):
    player_y = state["player_y"] 
    if player_y >= HEIGHT - 1 - GROUND_HEIGHT:
        state["state"] = "dead"
    player_y = min(player_y + 2, HEIGHT - 1 - GROUND_HEIGHT)
    create_and_draw_grid(state, set())
    state["player_y"] = player_y
    write_state(state)

def tick_command(args):
    state = read_state()
    match state["state"]:
        case "waiting":
            state["state"] = "ticking"
            handle_tick_running(state, args.selection_count)
        case "ticking":
            handle_tick_running(state, args.selection_count)
        case "dying" | "dead":
            handle_tick_dying(state)

def initialize_command(args):
    state = get_initial_state()
    initialize_buffers()
    create_and_draw_grid(state, set())
    if os.path.exists("log"):
        os.remove("log")
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
