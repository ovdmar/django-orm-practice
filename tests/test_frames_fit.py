#!/usr/bin/env python
"""Fullscreen only means something if a screen fits the window.

Builds both screens of every exercise (the task, and the result after the reference
solution runs) at several terminal sizes and checks that none is too tall - and that
no single line is too wide, since a wrapped line pushes the screen down just as badly.

Run:  .venv/bin/python tests/test_frames_fit.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ANSI = re.compile(r"\033\[[0-9;]*m")
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
            room, tallest, widest = session.screen_room(), 0, 0
            for ex in EXERCISES:
                session.enter_level(ex.level)   # so the progress strip is measured too
                session.current = ex
                reference = session.reference(ex)
                grade = engine.grade(ex, ex.solution, reference)
                for frame in (session.build_frame(ex, None), session.build_frame(ex, grade)):
                    tallest = max(tallest, len(frame))
                    if len(frame) > room:
                        failures.append((width, height, ex.number, "tall",
                                         len(frame), room))
                    for line in frame:
                        plain = len(ANSI.sub("", line))
                        widest = max(widest, plain)
                        if plain > int(width):
                            failures.append((width, height, ex.number, "wide",
                                             plain, int(width)))
            ok = tallest <= room and widest <= int(width)
            print(f"  {width}x{height}: tallest {tallest}/{room} lines, "
                  f"widest {widest}/{width} columns  {'ok' if ok else 'OVERFLOW'}")
    for width, height, number, kind, got, limit in failures[:10]:
        print(f"  FAIL {width}x{height} exercise #{number}: too {kind}, {got} vs {limit}")
    print("frames fit" if not failures else f"{len(failures)} overflowing screen(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
