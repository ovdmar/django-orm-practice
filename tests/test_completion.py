#!/usr/bin/env python
"""Tab completion: namespace names, attributes, and field paths.

The completer is driven directly here (its line reader is injectable), so the cases
are exact rather than scraped off a terminal; the last check runs the real CLI to
confirm tab is actually bound to it.

Run:  .venv/bin/python tests/test_completion.py
"""

import os
import pty
import select
import signal
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CASES = [
    # line typed so far,                                  word, expected completions
    ("Auth", "Auth", ["Author", "AuthorProfile"]),
    ("Prefe", "Prefe", ["Prefetch"]),
    ("Book.pub", "Book.pub",
     ["Book.published_date", "Book.publisher", "Book.publisher_id"]),
    ("Book.objects.select_r", "Book.objects.select_r", ["Book.objects.select_related"]),
    # a string argument: field paths on the model named last in the line
    ("Book.objects.values_list('pub", "pub", ["published_date", "publisher", "publisher_id"]),
    # select_related only joins forward FK/O2O, so published_date is not offered
    ("Book.objects.select_related('pub", "pub", ["publisher"]),
    ("Author.objects.prefetch_related('boo", "boo", ["books"]),
    ("Book.objects.order_by('-pric", "pric", ["price"]),
    # keyword arguments are field paths too, over as many __ hops as you like
    ("Author.objects.filter(firs", "firs", ["firstname"]),
    ("Author.objects.filter(books__reviews__rat", "books__reviews__rat",
     ["books__reviews__rating"]),
    ("Review.objects.filter(book__author__recommendedby__firstn",
     "book__author__recommendedby__firstn", ["book__author__recommendedby__firstname"]),
    # a lookup once the path reaches a plain field
    ("Book.objects.filter(price__gt", "price__gt", ["price__gt", "price__gte"]),
    # the nearest model wins, so a nested queryset completes against its own model
    ("Author.objects.prefetch_related(Prefetch('books', queryset=Book.objects.filter(pag",
     "pag", ["page_count"]),
]


def main():
    from practice.bootstrap import build_database

    build_database()
    from practice import engine
    from practice.complete import Completer

    namespace = engine.build_namespace()
    failures = 0
    for line, word, expected in CASES:
        completer = Completer(
            namespace, line_reader=lambda line=line, word=word: (line, len(line) - len(word)))
        got = completer.collect(word)
        ok = got == expected
        failures += 0 if ok else 1
        print(f"  {line[-52:]:<54} {'ok' if ok else 'FAIL got ' + repr(got[:6])}")

    # and tab really is wired to it in the running CLI
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(ROOT)
        os.environ.update(TERM="xterm", COLUMNS="150", LINES="45")
        os.execv(sys.executable, [sys.executable, "practice.py", "--only", "1", "--no-color"])
        os._exit(1)

    def drain(seconds):
        buf, end = b"", time.time() + seconds
        while time.time() < end:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    buf += os.read(master, 65536)
                except OSError:
                    break
        return buf.decode(errors="replace")

    seen, end = "", time.time() + 20
    while ">>> " not in seen and time.time() < end:
        seen += drain(0.4)
    os.write(master, b"Publi\t")
    out = drain(1.2)
    ok = "Publisher" in out
    failures += 0 if ok else 1
    print(f"  {'tab is bound in the CLI':<54} {'ok' if ok else 'FAIL ' + repr(out[-80:])}")
    try:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except OSError:
        pass

    print("completion ok" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
