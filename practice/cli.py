"""The REPL: show a task, read a query, grade it, repeat."""

import atexit
import codeop
import os
import readline
import sys

from practice import engine, progress
from practice.exercises import EXERCISES, SECTIONS, get

HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".history")

COMMANDS = """
  <query>        run it - multi-line is fine, keep typing until the statement is complete
  :s :solution   show the reference solution (and the lesson behind it)
  :hint          one hint at a time
  :n :next       next exercise            :p :prev      previous exercise
  :g N :goto N   jump to exercise N       :l :list      list all exercises
  :sql           the SQL your last attempt actually ran
  :diff          reference answer vs yours, for the last attempt
  :d :data       row counts in the database
  :m :models     the schema
  :stats         your progress            :reset        wipe saved progress
  :q :quit       leave (progress is saved after every attempt)
"""


class Ink:
    def __init__(self, enabled):
        self.on = enabled

    def __call__(self, code, text):
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def bold(self, t): return self("1", t)
    def dim(self, t): return self("2", t)
    def red(self, t): return self("31", t)
    def green(self, t): return self("32", t)
    def yellow(self, t): return self("33", t)
    def blue(self, t): return self("36", t)


class Session:
    def __init__(self, start=None, only=None, color=True):
        self.ink = Ink(color and sys.stdout.isatty() and os.environ.get("NO_COLOR") is None)
        self.data = progress.load()
        self.only = only
        self.number = start or self.data.get("current") or 1
        self.refs = {}          # slug -> reference Attempt
        self.last = None        # last graded Attempt
        self.last_grade = None
        self.hint_at = 0
        self.pending = None     # a line typed at the "next exercise" prompt

    # -- reference answers ------------------------------------------------- #
    def reference(self, ex):
        if ex.slug not in self.refs:
            ref = engine.run(ex.solution, ex.consume, ex.order_matters)
            if ref.error:
                print(self.ink.red(f"BUG: reference solution for {ex.slug} failed:\n{ref.error}"))
            self.refs[ex.slug] = ref
        return self.refs[ex.slug]

    # -- rendering --------------------------------------------------------- #
    def show(self, ex):
        ink, ref = self.ink, self.reference(ex)
        done = self.data["exercises"].get(ex.slug, {})
        badge = ""
        if done.get("solved"):
            best, target = done.get("best_queries"), done.get("target")
            mark = "solved" if best is not None and target is not None and best <= target else "solved (slow)"
            badge = ink.dim(f"  [{mark}, best {best}q]")
        print()
        print(ink.blue("─" * 78))
        print(ink.bold(f"{ex.number}/{len(EXERCISES)}  {ex.title}") +
              ink.dim(f"   [{ex.section}]") + badge)
        print(ink.blue("─" * 78))
        for line in ex.prompt.split("\n"):
            print("  " + line)
        contract = engine.source_of(ex.consume)
        if contract:
            print()
            print(ink.dim("  the grader consumes your result like this:"))
            for line in contract.split("\n"):
                print(ink.dim("    " + line))
        print()
        budget = f"  budget: {ref.nqueries} quer{'y' if ref.nqueries == 1 else 'ies'}"
        if ex.mutates:
            budget += ink.dim("   (writes are rolled back after every attempt)")
        print(ink.yellow(budget))
        if ex.hints:
            print(ink.dim(f"  {len(ex.hints)} hint(s) available - :hint"))

    def verdict(self, ex, grade):
        ink = self.ink
        att = grade.attempt
        if att.error and att.shape_error:
            print(ink.red("  ✗ the grader cannot read what you returned") +
                  ink.dim(f"   (you returned {att.raw})"))
            print("    " + att.error.split("\n")[-1])
            contract = engine.source_of(ex.consume)
            if contract:
                print(ink.dim("    it needs to work with:  ") + contract)
            return
        if att.error:
            print(ink.red("  ✗ your code raised"))
            for line in att.error.split("\n"):
                print("    " + line)
            return
        plural = "query" if grade.nqueries == 1 else "queries"
        if not grade.ok:
            print(ink.red(f"  ✗ wrong answer") + ink.dim(f"   ({grade.nqueries} {plural})"))
            print(ink.dim("    you returned: ") + engine.preview(att.value))
            ref = self.reference(ex)
            if isinstance(att.value, list) and isinstance(ref.value, list) and \
                    len(att.value) != len(ref.value):
                print(ink.dim(f"    {len(att.value)} items, the reference answer has {len(ref.value)}"))
            print(ink.dim("    :diff to compare with the reference answer, :hint, :s for the solution"))
            return
        if grade.better:
            print(ink.green(f"  ✓ correct in {grade.nqueries} {plural}") +
                  ink.bold(f" - better than the reference ({grade.target})! "))
        elif grade.optimal:
            print(ink.green(f"  ✓ correct, {grade.nqueries} {plural} - optimal"))
        else:
            print(ink.yellow(f"  ~ correct, but {grade.nqueries} {plural} instead of {grade.target}"))
            for n, shape in att.repeated_shapes()[:2]:
                print(ink.dim(f"    {n}x  ") + engine._trim(shape, 90))
            if att.repeated_shapes():
                print(ink.dim("    that repeated shape is the N+1 - fetch it up front instead"))
            print(ink.dim("    try again, or :s for the reference solution"))
        if ex.notes and (grade.optimal or grade.better):
            print(ink.dim("    " + ex.notes.replace("\n", "\n    ")))

    def solution(self, ex):
        ink, ref = self.ink, self.reference(ex)
        progress.mark_shown(self.data, ex)
        print(ink.bold("  reference solution:"))
        for line in ex.solution.split("\n"):
            print(ink.green("    " + line))
        print(ink.dim(f"    -> {ref.nqueries} quer{'y' if ref.nqueries == 1 else 'ies'}, "
                      f"answer: ") + engine.preview(ref.value, limit=3))
        if ex.notes:
            print()
            print(ink.dim("    " + ex.notes.replace("\n", "\n    ")))

    def diff(self, ex):
        ink, ref = self.ink, self.reference(ex)
        print(ink.dim("  reference answer:"))
        print("    " + engine.preview(ref.value, limit=8))
        if self.last is not None:
            print(ink.dim("  your last attempt:"))
            print("    " + engine.preview(self.last.value, limit=8))

    def listing(self):
        ink = self.ink
        section = None
        for ex in EXERCISES:
            if ex.section != section:
                section = ex.section
                print(ink.bold(f"\n{section}") + ink.dim(f"  - {SECTIONS[section]}"))
            d = self.data["exercises"].get(ex.slug, {})
            if d.get("solved"):
                ok = d.get("best_queries") is not None and d.get("target") is not None \
                     and d["best_queries"] <= d["target"]
                flag = ink.green(" ✓") if ok else ink.yellow(" ~")
            else:
                flag = ink.dim(" ·")
            print(f"{flag} {ex.number:>3}. {ex.title}")

    def stats(self):
        solved, clean, total = progress.summary(self.data, EXERCISES)
        attempts = sum(d.get("attempts", 0) for d in self.data["exercises"].values())
        shown = sum(1 for d in self.data["exercises"].values() if d.get("solution_shown"))
        print(f"  solved {solved}/{total}   within budget {clean}   "
              f"attempts {attempts}   solutions revealed {shown}")
        for name in SECTIONS:
            exs = [e for e in EXERCISES if e.section == name]
            s, c, t = progress.summary(self.data, exs)
            print(f"    {name:<18} {s:>3}/{t:<4} optimal {c}")

    def sql(self, limit=8):
        if self.last is None:
            print("  nothing run yet")
            return
        if not self.last.queries:
            print("  no queries at all")
            return
        seen, shown = {}, 0
        for i, q in enumerate(self.last.queries, 1):
            shape = next(s for s, qs in self.last.shape_counts().items() if q in qs)
            seen[shape] = seen.get(shape, 0) + 1
            if seen[shape] > 2 or shown >= limit:
                continue
            shown += 1
            print(self.ink.dim(f"  {i:>3}. {q['time']}s  ") + engine._trim(q["sql"], 140))
        hidden = len(self.last.queries) - shown
        if hidden:
            print(self.ink.dim(f"  ... {hidden} more query/queries not shown; "
                               f"{len(self.last.shape_counts())} distinct shape(s) in total:"))
            for n, shape in self.last.repeated_shapes()[:3]:
                print(self.ink.dim(f"      {n}x  ") + engine._trim(shape, 100))

    def data_summary(self):
        from practice import seed  # noqa: F401
        from django.apps import apps
        for model in sorted(apps.get_app_config("bookstore").get_models(), key=lambda m: m.__name__):
            print(f"  {model.__name__:<16} {model.objects.count():>6}")

    def models(self):
        from django.apps import apps
        ink = self.ink
        for model in apps.get_app_config("bookstore").get_models():
            print(ink.bold(f"\n  {model.__name__}"))
            for f in model._meta.get_fields():
                kind = type(f).__name__
                if f.is_relation:
                    target = f.related_model.__name__ if f.related_model else "?"
                    extra = ""
                    if getattr(f, "null", False):
                        extra = " null"
                    if f.auto_created and not f.concrete:
                        name = getattr(f, "get_accessor_name", lambda: f.name)()
                        print(ink.dim(f"    {name:<22} reverse {kind} -> {target}{extra}"))
                        continue
                    print(f"    {f.name:<22} {kind} -> {target}{extra}")
                else:
                    print(ink.dim(f"    {f.name:<22} {kind}"))

    # -- the loop ---------------------------------------------------------- #
    def run(self):
        try:
            readline.read_history_file(HISTORY)
        except OSError:
            pass
        readline.set_history_length(2000)
        atexit.register(lambda: readline.write_history_file(HISTORY))

        ink = self.ink
        print(ink.bold("django ORM practice") +
              ink.dim(f"   {len(EXERCISES)} exercises, in-memory sqlite, "
                      f"all models pre-imported"))
        print(ink.dim("  :h for commands, :q to quit"))
        current = get(self.number) or EXERCISES[0]
        self.hint_at = 0
        self.show(current)
        while True:
            try:
                code = self.read()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if code is None:
                continue
            if code.startswith(":") or code in ("?", "help"):
                nxt = self.command(code, current)
                if nxt == "quit":
                    break
                if isinstance(nxt, int):
                    target = get(nxt)
                    if target is None:
                        print(f"  no exercise {nxt}")
                        continue
                    current = target
                    self.hint_at, self.last = 0, None
                    progress.set_current(self.data, current.number)
                    self.show(current)
                continue
            grade = engine.grade(current, code, self.reference(current))
            self.last, self.last_grade = grade.attempt, grade
            progress.record_attempt(self.data, current, grade)
            self.verdict(current, grade)
            if grade.ok and self.only is None:
                nxt = get(current.number + 1)
                if nxt is None:
                    print(ink.bold("\n  that was the last one. :stats to see how it went."))
                    continue
                print(ink.dim("  [enter] next exercise, or keep working on this one"))
                try:
                    typed = input().strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if typed:
                    self.pending = typed
                    continue
                current = nxt
                self.hint_at, self.last = 0, None
                progress.set_current(self.data, current.number)
                self.show(current)
        progress.save(self.data)
        solved, clean, total = progress.summary(self.data, EXERCISES)
        print(ink.dim(f"  saved - {solved}/{total} solved, {clean} within budget"))

    def read(self):
        """Read one statement, continuing while it is syntactically incomplete."""
        compiler = codeop.CommandCompiler()
        lines = []
        if self.pending is not None:
            pending, self.pending = self.pending, None
            if pending.startswith(":") or pending in ("?", "help"):
                return pending
            lines.append(pending)
            try:
                if compiler(pending, "<answer>", "exec") is not None:
                    return pending
            except SyntaxError:
                return pending
        while True:
            line = input(self.ink.blue(">>> " if not lines else "... "))
            if not lines and (line.strip().startswith(":") or line.strip() in ("?", "help")):
                return line.strip()
            lines.append(line)
            source = "\n".join(lines)
            if not source.strip():
                return None
            try:
                if compiler(source, "<answer>", "exec") is not None:
                    return source
            except SyntaxError:
                return source        # let the engine report it
            if lines[-1].strip() == "":  # blank line ends a block
                return source

    def command(self, raw, ex):
        parts = raw.split()
        cmd = parts[0].lstrip(":")
        arg = parts[1] if len(parts) > 1 else None
        if cmd in ("q", "quit", "exit"):
            return "quit"
        if cmd in ("h", "help", "?"):
            print(COMMANDS)
        elif cmd in ("s", "solution"):
            self.solution(ex)
        elif cmd == "hint":
            if not ex.hints:
                print("  no hints for this one - :s shows the solution")
            elif self.hint_at >= len(ex.hints):
                print("  that was the last hint")
            else:
                print(self.ink.yellow(f"  hint: {ex.hints[self.hint_at]}"))
                self.hint_at += 1
        elif cmd in ("n", "next", "skip"):
            return ex.number + 1
        elif cmd in ("p", "prev"):
            return max(1, ex.number - 1)
        elif cmd in ("g", "goto"):
            if arg and arg.isdigit():
                return int(arg)
            print("  usage: :g 42")
        elif cmd in ("l", "list"):
            self.listing()
        elif cmd == "sql":
            self.sql()
        elif cmd == "diff":
            self.diff(ex)
        elif cmd in ("d", "data"):
            self.data_summary()
        elif cmd in ("m", "models"):
            self.models()
        elif cmd == "stats":
            self.stats()
        elif cmd == "reset":
            progress.reset()
            self.data = progress.load()
            print("  progress wiped")
        elif cmd in ("r", "repeat", "show"):
            self.show(ex)
        else:
            print(f"  unknown command {raw!r} - :h for the list")
        return None
