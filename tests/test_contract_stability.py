#!/usr/bin/env python
"""The grader contract on screen must be the one being run - and must not drift.

inspect.getsource() finds a lambda by line number and reads the file live, so
resolving the contract lazily showed a neighbouring exercise's lambda once the file
had been edited under a running session. Contracts are captured at import instead;
this edits a file underneath the loaded module to prove it.

Run:  .venv/bin/python tests/test_contract_stability.py
"""

import os
import pathlib
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TARGET = pathlib.Path(ROOT) / "practice/exercises/b_select_related.py"


def main():
    from practice.bootstrap import build_database

    build_database()
    from practice import engine
    from practice.exercises import EXERCISES

    failures = 0
    with_consume = [ex for ex in EXERCISES if ex.consume is not None]

    # 1. every contract parses and behaves exactly like the consume it stands for
    for ex in with_consume[:8] + with_consume[-8:]:
        reference = engine.run_for(ex, ex.solution)
        shown = engine.run(ex.solution, eval(ex.contract), ex.order_matters, ex.setup)
        ok = not shown.error and shown.value == reference.value
        failures += 0 if ok else 1
        print(f"  #{ex.number:>2} {ex.slug:<24} "
              f"{'ok' if ok else 'FAIL ' + (shown.error or 'different answer')}")

    # 2. shifting the file under the loaded module must not move the contracts
    before = {ex.number: ex.contract for ex in with_consume}
    original = TARGET.read_text()
    try:
        TARGET.write_text("# two\n# extra lines\n" + original)
        after = {ex.number: ex.contract for ex in with_consume}
        moved = [n for n in before if before[n] != after[n]]
        failures += 0 if not moved else 1
        print(f"  {'contracts survive an edit to the file':<29} "
              f"{'ok' if not moved else 'FAIL moved for ' + str(moved[:4])}")
    finally:
        TARGET.write_text(original)

    print("contracts stable" if not failures else f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
