#!/usr/bin/env python
"""How a snippet is submitted.

A complete expression runs the moment you press enter. Anything else - an assignment,
a loop, several statements - is collected like a file and a blank line runs it, so the
whole thing is measured as one unit.

Run:  .venv/bin/python tests/test_input_modes.py
"""

import os
import pty
import select
import signal
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTER = b"\r"
GRADED = ("✓ correct", "✗ wrong", "✗ your code raised", "~ correct")


class Cli:
    def __init__(self, exercise="1"):
        self.pid, self.master = pty.fork()
        if self.pid == 0:
            os.chdir(ROOT)
            os.environ.update(TERM="xterm", COLUMNS="150", LINES="45")
            os.environ.pop("NO_COLOR", None)
            os.execv(sys.executable, [sys.executable, "practice.py",
                                      "--only", exercise, "--no-color"])
            os._exit(1)
        self.banner = self.wait_for(">>> ", 20)

    def drain(self, seconds):
        buf, end = b"", time.time() + seconds
        while time.time() < end:
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
        return buf.decode(errors="replace")

    def wait_for(self, needle, seconds):
        seen, end = "", time.time() + seconds
        while needle not in seen and time.time() < end:
            seen += self.drain(0.4)
        return seen

    def send(self, data, wait=1.2):
        os.write(self.master, data)
        return self.drain(wait)

    def kill(self):
        for action in (lambda: os.kill(self.pid, signal.SIGKILL),
                       lambda: os.waitpid(self.pid, 0), lambda: os.close(self.master)):
            try:
                action()
            except OSError:
                pass


def check(name, condition, detail=""):
    print(f"  {name:<44} {'ok' if condition else 'FAIL ' + detail}")
    return 0 if condition else 1


def main():
    failures = 0

    cli = Cli()
    try:
        out = cli.send(b"Book.objects.all()" + ENTER, 2.0)
        failures += check("a complete expression runs on enter",
                          "✓ correct" in out, repr(out[-140:]))
    finally:
        cli.kill()

    cli = Cli()
    try:
        out = cli.send(b"qs = Book.objects.all()" + ENTER, 1.0)
        failures += check("an assignment waits for more",
                          not any(mark in out for mark in GRADED), repr(out[-110:]))
        failures += check("and says a blank line will run it",
                          "blank line runs it" in out, repr(out[-110:]))
        out = cli.send(b"qs" + ENTER, 0.8)
        failures += check("the trailing expression waits too",
                          not any(mark in out for mark in GRADED), repr(out[-110:]))
        out = cli.send(ENTER, 2.0)
        failures += check("the blank line runs the whole snippet",
                          "✓ correct" in out, repr(out[-140:]))
    finally:
        cli.kill()

    cli = Cli()
    try:
        cli.send(b":ml" + ENTER, 0.6)
        cli.send(b"Book.objects.all()" + ENTER, 0.6)      # would have run on its own
        out = cli.send(b"Book.objects.all()" + ENTER, 0.8)
        failures += check(":ml holds a complete expression back",
                          not any(mark in out for mark in GRADED), repr(out[-110:]))
        out = cli.send(ENTER, 2.0)
        failures += check("and the blank line runs it", "✓ correct" in out, repr(out[-140:]))
    finally:
        cli.kill()

    print("input modes ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
