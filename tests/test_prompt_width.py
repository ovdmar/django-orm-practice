#!/usr/bin/env python
"""Regression test: readline must know how wide the prompt really is.

A coloured prompt whose ANSI escapes are not wrapped in \001..\002 makes readline
count those bytes as visible columns. Relative moves still look fine, but as soon
as readline repositions absolutely (Ctrl-A, long lines, history recall) the visible
cursor lands N columns too far right and refuses to walk back over the first N
characters of your query.

Run:  .venv/bin/python tests/test_prompt_width.py
"""

import os
import pty
import re
import select
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PROMPT = ">>> "
TYPED = "ook.objects.all()"


def test_measured_width():
    from practice.cli import Ink

    for coloured in (True, False):
        prompt = Ink(coloured).rl("36", PROMPT)
        measured = re.sub("\001.*?\002", "", prompt, flags=re.S)
        assert len(measured) == len(PROMPT), (
            f"colour={coloured}: readline would measure {len(measured)} columns, "
            f"not {len(PROMPT)} - escapes need \\001..\\002 around them"
        )
    print(f"  readline measures the prompt as {len(PROMPT)} columns  ok")


def cursor_column(start, data):
    """Replay a byte stream through a minimal terminal and return the cursor column."""
    col, i = start, 0
    while i < len(data):
        byte = data[i:i + 1]
        if byte == b"\x1b":
            csi = re.match(rb"\x1b\[(\d*)([A-Za-z])", data[i:])
            if csi:
                n, kind = int(csi.group(1) or 1), csi.group(2)
                col += n if kind == b"C" else -n if kind == b"D" else 0
                if kind in (b"G", b"H"):
                    col = n - 1 if kind == b"G" else 0
                i += csi.end()
                continue
            other = re.match(rb"\x1b\][^\x07]*\x07", data[i:]) or re.match(rb"\x1b.", data[i:])
            i += other.end() if other else 1
            continue
        if byte in (b"\r", b"\n"):
            col = 0
        elif byte == b"\x08":
            col -= 1
        elif byte >= b" ":
            col += 1
        i += 1
    return col


def test_cursor_reaches_the_start():
    master, slave = pty.openpty()
    env = dict(os.environ, TERM="xterm", COLUMNS="120", LINES="40")
    env.pop("NO_COLOR", None)
    proc = subprocess.Popen([sys.executable, "practice.py", "--only", "1"],
                            cwd=ROOT, stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)

    def drain(seconds):
        buf, end = b"", time.time() + seconds
        while time.time() < end:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    buf += os.read(master, 65536)
                except OSError:
                    break
        return buf

    try:
        banner = drain(8.0)
        assert PROMPT.encode() in banner, "never reached the prompt"
        os.write(master, TYPED.encode())
        drain(0.6)
        os.write(master, b"\x01")                     # Ctrl-A, beginning of line
        stream = drain(0.8)
        column = cursor_column(len(PROMPT) + len(TYPED), stream)
        assert column == len(PROMPT), (
            f"after Ctrl-A the visible cursor sits in column {column}, "
            f"{column - len(PROMPT)} columns right of where the query starts"
        )
        print(f"  Ctrl-A puts the cursor in column {column}, where the query starts  ok")
        os.write(master, b"\r")
        drain(0.4)
        os.write(master, b":q\r")
        drain(1.0)
    finally:
        proc.terminate()
        os.close(master)


if __name__ == "__main__":
    failures = 0
    for test in (test_measured_width, test_cursor_reaches_the_start):
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    print("prompt width ok" if not failures else f"{failures} failure(s)")
    sys.exit(1 if failures else 0)
