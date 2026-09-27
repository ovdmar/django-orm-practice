"""Self-check: every reference solution must run, answer something, and beat its naive twin."""

from practice import engine
from practice.exercises import EXERCISES


def check(exercises=None, quiet=False):
    problems = []
    for ex in exercises or EXERCISES:
        ref = engine.run_for(ex, ex.solution)
        row = f"{ex.number:>3}. {ex.section[:9]:<9} {ex.slug:<26}"
        if ref.error:
            problems.append((ex, "reference raised", ref.error))
            print(f"{row} SOLUTION FAILED\n{ref.error}")
            continue
        if ref.value in (None, [], {}, 0):
            problems.append((ex, "empty answer", repr(ref.value)))
            print(f"{row} EMPTY ANSWER {ref.value!r}")
            continue
        note = ""
        if ex.naive:
            nv = engine.run_for(ex, ex.naive)
            if nv.error:
                problems.append((ex, "naive raised", nv.error))
                note = "  NAIVE FAILED: " + nv.error.splitlines()[-1]
            elif nv.value != ref.value:
                problems.append((ex, "naive disagrees", ""))
                note = "  NAIVE DISAGREES with reference"
            elif nv.nqueries <= ref.nqueries:
                problems.append((ex, "naive not slower", f"{nv.nqueries} vs {ref.nqueries}"))
                note = f"  NAIVE NOT SLOWER ({nv.nqueries} vs {ref.nqueries})"
            else:
                note = f"  naive={nv.nqueries}"
        if ex.consume is not None:
            if not ex.contract:
                problems.append((ex, "consume source unavailable", ""))
            else:
                # what the screen shows must be what the grader runs
                shown = engine.run(ex.solution, eval(ex.contract),
                                   ex.order_matters, ex.setup)
                if shown.error or shown.value != ref.value:
                    problems.append((ex, "displayed contract disagrees",
                                     shown.error or "a different answer"))
        good = bad = 0
        for kind, code, _why in ex.alternatives:
            alt = engine.run_for(ex, code)
            right = alt.error is None and alt.value == ref.value
            if kind in ("good", "careful"):
                good += 1
                if not right:
                    problems.append((ex, f"'{kind}' alternative is wrong",
                                     alt.error or "a different answer"))
                elif alt.nqueries > ref.nqueries:
                    problems.append((ex, f"'{kind}' alternative costs more",
                                     f"{alt.nqueries} vs {ref.nqueries}"))
            else:
                bad += 1
                if right and alt.nqueries <= ref.nqueries:
                    problems.append((ex, "'bad' alternative is actually fine", code))
        if not ex.alternatives:
            problems.append((ex, "no alternatives", ""))
        elif not bad:
            problems.append((ex, "no 'bad' alternative", ""))
        if not quiet:
            n = len(ref.value) if isinstance(ref.value, (list, dict)) else 1
            alts = f"  alts {good}+{bad}" if ex.alternatives else ""
            print(f"{row} {ref.nqueries:>3}q  rows={n:<5}{note}{alts}")
    total = len(exercises or EXERCISES)
    print(f"\n{total - len(problems)}/{total} ok, {len(problems)} problems")
    for ex, kind, detail in problems:
        print(f"  ! {ex.number} {ex.slug}: {kind} {detail.splitlines()[-1] if detail else ''}")
    return problems
