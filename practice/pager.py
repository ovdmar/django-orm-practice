"""Full-screen preview of a long answer, via the system pager (q to leave)."""

import os
import shlex
import subprocess
import sys


def page(text, title=None):
    if title:
        text = f"{title}\n{'-' * len(title)}\n{text}"
    if not (sys.stdout.isatty() and sys.stdin.isatty()):
        print(text)
        return
    for command in (os.environ.get("PAGER"), "less -SR", "more"):
        if not command:
            continue
        try:
            subprocess.run(shlex.split(command), input=text, text=True, check=False)
            return
        except OSError:
            continue
    print(text)
