#!/usr/bin/env python
"""Alt/Ctrl + up/down must step through the screens of the session.

readline owns the input line, so the navigation is wired as a readline macro that
submits ':back'/':fwd'. This drives a real pty and checks the escape sequences the
common terminals send actually move the screen - and that plain up/down is left
alone for command history.

Run:  .venv/bin/python tests/test_screen_history.py
"""

import os
import pty
import re
import select
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALT_UP, ALT_DOWN = b"\x1b[1;3A", b"\x1b[1;3B"
CTRL_UP = b"\x1b[1;5A"
ESC_PREFIX_UP = b"\x1b\x1b[A"
PLAIN_UP = b"\x1b[A"
SUBMIT = b"\x1b\r"          # alt+enter: Enter now adds a line instead of running


class Cli:
    def __init__(self):
        self.master, slave = pty.openpty()
        env = dict(os.environ, TERM="xterm", COLUMNS="150", LINES="45")
        env.pop("NO_COLOR", None)
        self.proc = subprocess.Popen(
            [sys.executable, "practice.py", "--from", "54", "--no-color"],
            cwd=ROOT, stdin=slave, stdout=slave, stderr=slave, env=env)
        os.close(slave)

    def drain(self, seconds):
        buf, end = b"", time.time() + seconds
        while time.time() < end:
            if select.select([self.master], [], [], 0.05)[0]:
                try:
                    buf += os.read(self.master, 65536)
                except OSError:
                    break
        return buf.decode(errors="replace")

    def send(self, data, wait=1.2):
        os.write(self.master, data)
        return self.drain(wait)

    def close(self):
        try:
            os.write(self.master, b"\x03:q" + SUBMIT)
            self.drain(0.8)
        except OSError:
            pass
        self.proc.terminate()
        os.close(self.master)


def screens(text):
    return re.findall(r"screen (\d+)/(\d+)", text)


def main():
    cli = Cli()
    failures = []
    try:
        assert ">>> " in cli.drain(8.0), "never reached the prompt"
        cli.send(b"Author.objects.filter(pk__lte=20)" + SUBMIT, 1.5)   # a second screen

        for name, key, expected in (
            ("alt+up", ALT_UP, ("1", "2")),
            ("alt+down", ALT_DOWN, ("2", "2")),
            ("ctrl+up", CTRL_UP, ("1", "2")),
            ("esc-prefixed up", ESC_PREFIX_UP, None),   # already at the oldest
        ):
            out = cli.send(key)
            seen = screens(out)
            if expected is None:
                ok = bool(seen) or "oldest screen" in out
            else:
                ok = seen == [expected]
            print(f"  {name:<18} {'ok' if ok else 'FAIL: ' + repr(out[-120:])}")
            if not ok:
                failures.append(name)

        # plain up must still recall the previous command, not move screens
        out = cli.send(PLAIN_UP, 0.8)
        if screens(out):
            failures.append("plain up moved the screen instead of recalling history")
            print("  plain up           FAIL - stole history")
        else:
            print("  plain up           ok - left to readline history")
    finally:
        cli.close()
    print("screen history ok" if not failures else f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
