#!/usr/bin/env python3

import os
import sys
import json
import os.path
import time
import subprocess
from datetime import datetime
import argparse

WIDTH = 15
HEIGHT = 15
PIPE_WIDTH = 3
PLAYER_X = 3
TARGET_FPS = 4
TARGET_FRAMETIME = 1.0 / TARGET_FPS

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
EYES   = "👀"
#EYES   = "👁️"

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
             "flapped_on_prior_frame": False
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
    
def add_pipes_to_grid(grid, frame):
    for (is_top, locations) in ((True, TOP), (False, BOTTOM)):
        for (x, height) in locations:
            x = x - frame
            for pipe_x in range(x, x + PIPE_WIDTH):
                if pipe_x < 0: continue
                if pipe_x >= WIDTH: continue
                for pipe_y in range(height):
                    color = BROWN if pipe_y + 2 == height else GREEN
                    pipe_y = pipe_y if is_top else -pipe_y - 1
                    grid[pipe_y][pipe_x] = color

def add_player_to_grid(grid, state):
    player_y = state["player_y"]
    fall_speed = state["fall_speed"]

    if fall_speed == 2 and False:
        # eyes in bottom right instead of emphasize that we're falling
        # It feels like we should be able to do something like this but it ends
        # up looking weird, I think because the orientation of the eyes emoji
        # doesn't change.
        # g
        grid[player_y][PLAYER_X] = YELLOW
        grid[player_y][PLAYER_X-1] = YELLOW
        if player_y < HEIGHT - 1:
            grid[player_y + 1][PLAYER_X] = EYES
            grid[player_y + 1][PLAYER_X-1] = ORANGE
    else:
        grid[player_y][PLAYER_X] = EYES
        #folder = WING1
        #if state["frame"] % 2 == 0: folder = WING2
        grid[player_y][PLAYER_X-1] = WHITE
        if player_y < HEIGHT - 1:
            grid[player_y + 1][PLAYER_X] = ORANGE
            grid[player_y + 1][PLAYER_X-1] = YELLOW

def draw_grid(state, grid):
    write_to_buf1 = state["write_to_buf1"]
    target_dir = buffer_to_write_to(state)
    files = sorted(
            (file for file in os.listdir(target_dir) if not file.startswith(".")),
            key=lambda x:int(x.split(" ")[-1]))

    for idx, (file, grid) in enumerate(zip(files, grid)):
        file = os.path.join(target_dir, file)
        grid = "".join(grid)
        grid = os.path.join(target_dir, f"{grid} {idx}")

        # We touch the file to ensure its mtime gets updated
        if file != grid: os.rename(file, grid)
        else: subprocess.check_output(["touch", file])
    
    # This is how applescript knows which directory to flip to
    print(target_dir.split("/")[-1])
    state["write_to_buf1"] = not write_to_buf1

def create_and_draw_grid(state):
    grid = [[BLUE for _ in range(WIDTH)] for _ in range(HEIGHT)]
    add_pipes_to_grid(grid, state["frame"])
    add_player_to_grid(grid, state)
    draw_grid(state, grid)

def initialize_command(args):
    state = get_initial_state()
    initialize_buffers()
    create_and_draw_grid(state)
    write_state(state)

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

def sleep_command(args):
    state = read_state()
    start_of_frame = state["tick_start_time"]

    if start_of_frame is not None:
        now = datetime.now()
        time_spent_on_frame = (now - start_of_frame).total_seconds()
        diff = TARGET_FRAMETIME - time_spent_on_frame

        with open("log", "a") as f:
            f.write(f"FRAMETIME: {time_spent_on_frame}\n")

        if diff > 0:
            time.sleep(diff)

    state["tick_start_time"] = datetime.now()
    write_state(state)

    if state["frame"] < 40:
        print("continue")
    else:
        print("exit")

def tick_command(args):
    state = read_state()
    count = args.selection_count
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

    create_and_draw_grid(state)
    state["frame"] += 1
    write_state(state)

def start_frame_command(args):
    state = read_state()
    state["tick_start_time"] = datetime.now()
    write_state(state)

def main():
    parser = argparse.ArgumentParser(description="Run foldy bird")

    subparsers = parser.add_subparsers(title="commands", dest="command")

    initialize_parser = subparsers.add_parser("init", help="Initialize foldy bird")
    initialize_parser.set_defaults(func=initialize_command)

    tick_parser = subparsers.add_parser("tick", help="Run a game tick")
    tick_parser.add_argument("selection_count", type=int, help="Number of files selected")
    tick_parser.set_defaults(func=tick_command)

    await_parser = subparsers.add_parser("await", help="Await game start")
    await_parser.set_defaults(func=await_command)

    sleep_parser = subparsers.add_parser("sleep", help="Sleep between ticks")
    sleep_parser.set_defaults(func=sleep_command)

    start_frame = subparsers.add_parser("start-frame", help="Initialize the frame")
    start_frame.set_defaults(func=start_frame_command)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
