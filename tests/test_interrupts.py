#!/usr/bin/env python
"""ctrl+c clears the line; ctrl+d and exit() are how you leave.

Uses pty.fork() rather than subprocess: the child has to be a session leader with
the pty as its controlling terminal, or a ^C on that pty never becomes a SIGINT
for it and the test would prove nothing.

Run:  .venv/bin/python tests/test_interrupts.py
"""

import os
import pty
import select
import signal
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMIT = b"\r"              # a complete expression runs on enter


class Cli:
    def __init__(self, *args):
        self.pid, self.master = pty.fork()
        if self.pid == 0:                                   # child
            os.chdir(ROOT)
            os.environ.update(TERM="xterm", COLUMNS="150", LINES="45")
            os.environ.pop("NO_COLOR", None)
            os.execv(sys.executable,
                     [sys.executable, "practice.py", "--no-color", *args])
            os._exit(1)

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

    def send(self, data, wait=1.0):
        os.write(self.master, data)
        return self.drain(wait)

    def alive(self):
        pid, _status = os.waitpid(self.pid, os.WNOHANG)
        return pid == 0

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
    print(f"  {name:<34} {'ok' if condition else 'FAIL ' + detail}")
    return not condition


def main():
    failures = 0

    cli = Cli("--only", "1")
    try:
        cli.drain(8.0)
        out = cli.send(b"Book.objects.fil\x03")            # half a query, then ^C
        failures += check("ctrl+c keeps the session", cli.alive())
        failures += check("ctrl+c says the line is cleared", "line cleared" in out,
                          repr(out[-120:]))
        out = cli.send(b"Book.objects.all()" + SUBMIT, 2.0)   # leftovers would break this
        failures += check("the abandoned line is gone", "✓ correct" in out,
                          repr(out[-160:]))
        out = cli.send(b"\x03", 0.8)
        failures += check("a second ctrl+c stays quiet", "line cleared" not in out)
        failures += check("still running after two ctrl+c", cli.alive())
    finally:
        cli.kill()

    cli = Cli("--only", "1")
    try:
        cli.drain(8.0)
        # a runaway comprehension: ^C must abort the run, not the session
        cli.send(b"sum(1 for _ in range(10**10)) and Book.objects.all()" + SUBMIT, 1.5)
        out = cli.send(b"\x03", 2.0)
        failures += check("ctrl+c aborts a running query", "interrupted" in out,
                          repr(out[-120:]))
        failures += check("the session survives that", cli.alive())
        out = cli.send(b"Book.objects.all()" + SUBMIT, 2.5)
        failures += check("and still grades afterwards", "correct" in out,
                          repr(out[-120:]))
    finally:
        cli.kill()

    cli = Cli("--only", "1")
    try:
        cli.drain(8.0)
        out = cli.send(b"exit()" + SUBMIT, 2.0)
        failures += check("exit() leaves", "saved -" in out, repr(out[-120:]))
        time.sleep(0.3)
        failures += check("exit() ends the process", not cli.alive())
    finally:
        cli.kill()

    cli = Cli("--only", "1")
    try:
        cli.drain(8.0)
        out = cli.send(b"\x04", 2.0)
        failures += check("ctrl+d leaves", "saved -" in out, repr(out[-120:]))
        time.sleep(0.3)
        failures += check("ctrl+d ends the process", not cli.alive())
    finally:
        cli.kill()

    print("interrupts ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
