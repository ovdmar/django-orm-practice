#!/usr/bin/env python
"""Entry point: python practice.py [options]"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(
        description="Django ORM practice: solve it, then solve it in fewer queries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="with no options it resumes where you left off",
    )
    ap.add_argument("-f", "--from", dest="start", type=int, metavar="N",
                    help="start at exercise N")
    ap.add_argument("-o", "--only", type=int, metavar="N",
                    help="work on exercise N alone, do not advance")
    ap.add_argument("--level", choices=["easy", "medium", "hard"],
                    help="start at the first exercise of a difficulty")
    ap.add_argument("-s", "--section", choices=["basics", "select_related",
                                                "prefetch_related", "advanced"],
                    help="start at the first exercise of a section")
    ap.add_argument("-l", "--list", action="store_true", help="list the exercises and exit")
    ap.add_argument("--restart", action="store_true", help="wipe saved progress and start at 1")
    ap.add_argument("--verify", action="store_true",
                    help="run every reference solution and report query budgets")
    ap.add_argument("--data", action="store_true", help="print row counts and exit")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--no-schema", action="store_true", help="hide the schema reminder")
    ap.add_argument("--no-keys", action="store_true", help="hide the shortcut bar")
    ap.add_argument("--no-fullscreen", action="store_true",
                    help="let screens scroll past each other instead of replacing")
    args = ap.parse_args()

    from practice.bootstrap import build_database

    quiet = args.list and not args.verify
    if not quiet:
        print("loading fixtures into an in-memory sqlite db ...", end=" ", flush=True)
    counts = build_database()
    if not quiet:
        print(f"{sum(counts.values())} rows")

    from practice import progress
    from practice.cli import Session
    from practice.exercises import EXERCISES

    if args.restart:
        progress.reset()
    if args.verify:
        from practice.verify import check
        return 1 if check() else 0
    if args.data:
        for name, n in counts.items():
            print(f"  {name:<20} {n:>6}")
        return 0

    start = args.only or args.start
    if args.section and not start:
        start = next(e.number for e in EXERCISES if e.section == args.section)
    if args.level and not start:
        start = next(e.number for e in EXERCISES if e.level == args.level)
    if start is None:
        data = progress.load()
        start = data.get("current") or progress.first_unsolved(data, EXERCISES)
    session = Session(start=start, only=args.only, color=not args.no_color)
    if args.no_schema:
        session.show_schema = False
    if args.no_keys:
        session.show_keys = False
    if args.no_fullscreen:
        session.fullscreen = False
    if args.list:
        session.listing()
        return 0
    session.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
