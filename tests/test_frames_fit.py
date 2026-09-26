#!/usr/bin/env python
"""Fullscreen only means something if a screen fits the window.

Builds both screens of every exercise (the task, and the result after the reference
solution runs) at several terminal heights and checks none of them overflows.

Run:  .venv/bin/python tests/test_frames_fit.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

HEIGHTS = (24, 30, 45, 60)
WIDTHS = ("100", "150", "200")


def main():
    from practice.bootstrap import build_database

    build_database()
    from practice import engine
    from practice.cli import Session
    from practice.exercises import EXERCISES

    failures = []
    for width in WIDTHS:
        for height in HEIGHTS:
            os.environ["COLUMNS"], os.environ["LINES"] = width, str(height)
            session = Session(start=1, color=False)
            room, tallest = max(8, height - 3), 0
            for ex in EXERCISES:
                reference = session.reference(ex)
                grade = engine.grade(ex, ex.solution, reference)
                for frame in (session.build_frame(ex, None), session.build_frame(ex, grade)):
                    tallest = max(tallest, len(frame))
                    if len(frame) > room:
                        failures.append((width, height, ex.number, len(frame), room))
            print(f"  {width}x{height}: tallest screen {tallest} lines, room {room}  "
                  f"{'ok' if tallest <= room else 'OVERFLOW'}")
    for width, height, number, got, room in failures[:10]:
        print(f"  FAIL {width}x{height} exercise #{number}: {got} lines in {room}")
    print("frames fit" if not failures else f"{len(failures)} overflowing screen(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
