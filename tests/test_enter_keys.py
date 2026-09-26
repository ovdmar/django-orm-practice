#!/usr/bin/env python
"""Enter adds a line to the snippet; a submit key runs it.

Shift+Enter is only distinguishable in terminals that implement the kitty keyboard
protocol or xterm's modifyOtherKeys, so alt+enter and ctrl+j are bound as well -
this checks every one of them, and that a plain Enter submits nothing.

Run:  .venv/bin/python tests/test_enter_keys.py
"""

import os
import pty
import select
import signal
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHIFT_ENTER_KITTY = b"\x1b[13;2u"
SHIFT_ENTER_XTERM = b"\x1b[27;2;13~"
ALT_ENTER = b"\x1b\r"
CTRL_J = b"\n"
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
        self.banner = self.wait_for("shift+enter = run", 20)

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

    def send(self, data, wait=1.0):
        os.write(self.master, data)
        return self.drain(wait)

    def kill(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        try:
            os.close(self.master)
        except OSError:
            pass


def check(name, condition, detail=""):
    print(f"  {name:<40} {'ok' if condition else 'FAIL ' + detail}")
    return 0 if condition else 1


def main():
    failures = 0

    cli = Cli()
    try:
        failures += check("the reminder sits above the prompt",
                          "enter = new line" in cli.banner)
        out = cli.send(b"qs = Book.objects.all()" + ENTER, 1.0)
        failures += check("enter alone submits nothing",
                          not any(mark in out for mark in GRADED), repr(out[-100:]))
        out = cli.send(b"qs" + ALT_ENTER, 2.0)
        failures += check("alt+enter runs the two-line snippet",
                          "✓ correct" in out, repr(out[-140:]))
    finally:
        cli.kill()

    for name, key in (("shift+enter (kitty protocol)", SHIFT_ENTER_KITTY),
                      ("shift+enter (xterm modifyOtherKeys)", SHIFT_ENTER_XTERM),
                      ("ctrl+j", CTRL_J)):
        cli = Cli()
        try:
            cli.send(b"qs = Book.objects.all()" + ENTER, 0.6)
            out = cli.send(b"qs" + key, 2.0)
            failures += check(f"{name} runs it", "✓ correct" in out, repr(out[-140:]))
        finally:
            cli.kill()

    print("enter keys ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
