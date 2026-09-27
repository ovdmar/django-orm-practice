#!/usr/bin/env python
"""An exercise number must mean the same thing on every clone.

Feedback arrives as "exercise #12 is wrong", so #12 has to be the same exercise for
whoever sent it: numbering may not depend on local state, and adding an exercise must
not renumber the ones already there.

Run:  .venv/bin/python tests/test_numbering.py
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def check(name, condition, detail=""):
    print(f"  {name:<52} {'ok' if condition else 'FAIL ' + detail}")
    return 0 if condition else 1


def main():
    from practice.bootstrap import build_database

    build_database()
    from practice import progress
    from practice.exercises import EXERCISES, _base, a_basics, b_select_related
    from practice.exercises import c_prefetch, d_advanced
    from practice.exercises._base import Exercise as E

    modules = (a_basics, b_select_related, c_prefetch, d_advanced)
    failures = 0
    baseline = {ex.slug: ex.number for ex in EXERCISES}

    failures += check("numbers run 1..N in order",
                      all(ex.number == i + 1 for i, ex in enumerate(EXERCISES)))
    failures += check("slugs are unique", len({ex.slug for ex in EXERCISES}) == len(EXERCISES))

    # solved/level state must not move a single number
    data = progress.load()
    for ex in EXERCISES[:20]:
        progress.entry(data, ex.slug).update(solved=True, best_queries=1, target=1)
    data["level"] = "hard"
    progress.save(data)
    again = {ex.slug: ex.number for ex in _base.collect(*modules)}
    failures += check("progress and practice mode change nothing", again == baseline)
    progress.reset()

    # an exercise added later lands at the end, wherever it is written
    newcomer = E(slug="added-later", section="basics", title="Written next month",
                 prompt="...", solution="Book.objects.all()", added="2099-01-01")
    a_basics.EXERCISES.insert(3, newcomer)          # deliberately in the middle
    try:
        grown = _base.collect(*modules)
        after = {ex.slug: ex.number for ex in grown}
        moved = [slug for slug in baseline if baseline[slug] != after[slug]]
        failures += check("a new exercise takes the next free number",
                          after["added-later"] == len(grown), str(after["added-later"]))
        failures += check("and renumbers none of the existing ones", not moved, str(moved[:5]))
    finally:
        a_basics.EXERCISES.remove(newcomer)
        _base.collect(*modules)

    restored = {ex.slug: ex.number for ex in _base.collect(*modules)}
    failures += check("removing it restores the numbering", restored == baseline)

    print("numbering stable" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
