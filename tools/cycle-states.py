#!/usr/bin/env python3
"""Drive the running status bar app through every Daisy state so you can watch it in the menu bar.

    ./tools/cycle-states.py                 # cycle everything, 7 s each, loop forever
    ./tools/cycle-states.py --dwell 15      # linger longer on each
    ./tools/cycle-states.py --once          # one pass, then clean up
    ./tools/cycle-states.py --hold zoomies  # park on one clip and stay there
    ./tools/cycle-states.py --list          # show the state -> clip mapping and exit

Works by writing a synthetic session file into ~/.claude/statusbar/state.d/, which is exactly what
hooks/update.js does on a real hook event. Nothing is faked inside the app: it polls that directory,
so what you see is the real state machine reacting to real input.

The file carries THIS script's pid, and the app treats a session as live via kill(pid, 0). So while
this runs the app will not idle-quit, and you do not need an active Claude Code session.

Ctrl-C removes the file and hands the menu bar back.
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "statusbar" / "state.d"
SESSION_ID = "zz-daisy-debug"          # sorts last; never collides with a real session id
STATE_FILE = STATE_DIR / f"{SESSION_ID}.json"

# (menu bar label, state, raw tool name, clip the driver should choose)
SEQUENCE = [
    ("Thinking",            "thinking",   "",          "trot"),
    ("Reading a file",      "tool",       "Read",      "sniff"),
    ("Searching",           "tool",       "Grep",      "sniff"),
    ("Editing",             "tool",       "Edit",      "dig"),
    ("Writing",             "tool",       "Write",     "dig"),
    ("Running command",     "tool",       "Bash",      "zoomies"),
    ("Delegating",          "tool",       "Task",      "trot (fallback)"),
    ("Awaiting permission", "permission", "",          "ask"),
    ("Done",                "done",       "",          "wag, then drowsy"),
    ("Idle",                "idle",       "",          "drowsy, then sleep after 2 min"),
]

BY_CLIP = {
    "trot": ("Thinking", "thinking", ""),
    "sniff": ("Reading a file", "tool", "Read"),
    "dig": ("Editing", "tool", "Edit"),
    "zoomies": ("Running command", "tool", "Bash"),
    "ask": ("Awaiting permission", "permission", ""),
    "wag": ("Done", "done", ""),
    "drowsy": ("Idle", "idle", ""),
    "sleep": ("Idle", "idle", ""),
}


def write_state(label: str, state: str, tool: str) -> None:
    now = int(time.time())
    payload = {
        "state": state,
        "label": label,
        "tool": tool,
        "project": "daisy-debug",
        "cwd": str(Path.cwd()),
        "sessionId": SESSION_ID,
        "transcript": "",
        "entrypoint": "cli",
        "term_program": "Apple_Terminal",
        "pid": os.getpid(),          # our own pid: the app's kill(pid,0) liveness probe passes
        "started": True,
        "startedAt": now if state in ("thinking", "tool") else 0,
        "ts": now,
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(STATE_FILE)          # atomic, so the app never reads a half-written file


def cleanup(*_) -> None:
    try:
        STATE_FILE.unlink()
    except FileNotFoundError:
        pass
    print("\ncleaned up — menu bar handed back")
    sys.exit(0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Cycle the menu bar through every Daisy state.")
    ap.add_argument("--dwell", type=float, default=7.0, help="seconds per state (default 7)")
    ap.add_argument("--once", action="store_true", help="one pass instead of looping")
    ap.add_argument("--hold", metavar="CLIP", help=f"park on one clip: {', '.join(BY_CLIP)}")
    ap.add_argument("--list", action="store_true", help="print the mapping and exit")
    args = ap.parse_args()

    if args.list:
        print(f"{'menu bar label':22s} {'state':11s} {'tool':8s} clip")
        for label, state, tool, clip in SEQUENCE:
            print(f"{label:22s} {state:11s} {tool or '-':8s} {clip}")
        return 0

    if not STATE_DIR.parent.exists():
        sys.exit(f"{STATE_DIR.parent} does not exist — is the status bar app installed?")

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    if args.hold:
        if args.hold not in BY_CLIP:
            sys.exit(f"unknown clip {args.hold!r}. choose from: {', '.join(BY_CLIP)}")
        label, state, tool = BY_CLIP[args.hold]
        write_state(label, state, tool)
        print(f"holding '{args.hold}'  (state={state} tool={tool or '-'})")
        print("Ctrl-C to stop and clean up.")
        while True:
            time.sleep(1)
            write_state(label, state, tool)   # refresh ts so the session stays the most recent

    print(f"cycling {len(SEQUENCE)} states, {args.dwell:g}s each. Ctrl-C to stop.", flush=True)
    print("NOTE: a real Claude Code session that is thinking outranks this one, so watch the menu")
    print("      bar with Claude idle, or expect the occasional hijack.\n")
    passes = 0
    while True:
        for label, state, tool, clip in SEQUENCE:
            write_state(label, state, tool)
            print(f"  {label:22s} state={state:11s} tool={tool or '-':8s} -> expect: {clip}", flush=True)
            deadline = time.time() + args.dwell
            while time.time() < deadline:
                time.sleep(0.5)
                write_state(label, state, tool)   # keep ts fresh so we stay the lead session
        passes += 1
        if args.once:
            break
        print(f"  --- pass {passes} complete, looping ---\n", flush=True)
    cleanup()


if __name__ == "__main__":
    sys.exit(main())
