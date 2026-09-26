"""The REPL: show a task, read a query, grade it, repeat."""

import atexit
import os
import re
import readline
import shutil
import textwrap
import sys

from practice import engine, pager, progress, schema
from practice.exercises import EXERCISES, SECTIONS, get

HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".history")

COMMANDS = """
  <query>        an expression runs as soon as you hit enter. Anything else (assignment,
                 loop, several statements) is collected like a file - dedent to close a
                 block - and a blank line runs the whole snippet as one measured unit
  :ml :multi     start a multi-statement snippet (or end a line with \\), blank line runs it
  :s :solution   show the reference solution (and the lesson behind it)
  :hint          one hint at a time
  :n :next       next exercise            :p :prev      previous exercise
  :g N :goto N   jump to exercise N       :l :list      list all exercises
  :v :view       full-screen preview of your answer (q to leave)
                 :v ref  the reference answer      :v sql  every query it ran
  :sql           the SQL your last attempt actually ran
  :diff          reference answer vs yours, for the last attempt
  :d :data       row counts in the database
  :m :models     the whole schema      :sc :schema  toggle the schema reminder
  :lay :layout   cycle the column layout (auto / 3 / 2 / stack)
  :k :keys       show/hide the shortcut bar above each exercise
  :stats         your progress            :reset        wipe saved progress
  :q :quit       leave (progress is saved after every attempt)
"""


KEYS = [
    (":h", "help"), (":s", "solution"), (":hint", ""), (":v", "view all (q exits)"),
    (":diff", ""), (":sql", ""), (":n", "next"), (":p", "prev"), (":g N", "goto"),
    (":l", "list"), (":m", "models"), (":sc", "schema"), (":lay", "layout"),
    (":ml", "multi-line (blank line runs)"), (":stats", ""), (":q", "quit"),
]


class Ink:
    def __init__(self, enabled):
        self.on = enabled

    def __call__(self, code, text):
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def rl(self, code, text):
        """A coloured readline prompt.

        The escapes must sit between \001 and \002 or readline counts them as
        visible width, and every cursor move is then off by that many columns.
        """
        return f"\001\033[{code}m\002{text}\001\033[0m\002" if self.on else text

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
        self.told_multiline = False
        self.show_schema = self.data.get("schema", True)
        self.layout = self.data.get("layout", "auto")
        self.show_keys = self.data.get("keys", True)

    def revealed(self, ex):
        """Has the name of the technique stopped being a spoiler?"""
        d = self.data["exercises"].get(ex.slug, {})
        return bool(d.get("solved") or d.get("solution_shown"))

    def label(self, ex):
        return f"Exercise #{ex.number}" + (f" - {ex.title}" if self.revealed(ex) else "")

    # -- reference answers ------------------------------------------------- #
    def reference(self, ex):
        if ex.slug not in self.refs:
            ref = engine.run(ex.solution, ex.consume, ex.order_matters)
            if ref.error:
                print(self.ink.red(f"BUG: reference solution for {ex.slug} failed:\n{ref.error}"))
            self.refs[ex.slug] = ref
        return self.refs[ex.slug]

    # -- rendering --------------------------------------------------------- #
    # -- layout ------------------------------------------------------------ #
    def _plan(self, has_result):
        """Which columns fit, and how wide. None means stack everything."""
        w = shutil.get_terminal_size((80, 24)).columns
        lay, sch = self.layout, self.show_schema
        if lay == "stack" or w < 96:
            return None, w
        if not has_result:
            return ([("task", min(62, w - 44)), ("schema", 38)] if sch else None), w
        if sch and w >= 104 and (lay == "3" or (lay == "auto" and w >= 130)):
            task_w = 34 if w >= 130 else 28
            return [("task", task_w), ("result", w - task_w - 38 - 7), ("schema", 38)], w
        if sch and lay in ("auto", "3", "2"):
            return [("result", w - 41), ("schema", 38)], w
        return [("result", w - 3)], w

    def _keybar(self, width):
        """Pack the shortcut list into lines without ever splitting an item."""
        width = max(40, width)
        lines, current = [], ""
        for key, label in KEYS:
            item = f"{key} {label}".strip()
            candidate = f"{current}   {item}" if current else item
            if len(candidate) > width:
                lines.append(current)
                current = item
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _clip(text, width):
        text = text.rstrip()
        return text if len(text) <= width else text[: width - 1] + "…"

    def _grid(self, cells, plan):
        """cells: {column name: [(text, style), ...]} clipped into place."""
        ink = self.ink
        height = max((len(cells.get(name, [])) for name, _w in plan), default=0)
        for i in range(height):
            parts = []
            for name, w in plan:
                text, style = (cells.get(name, []) + [("", None)] * height)[i]
                text = self._clip(text, w)
                parts.append((style(text) if style else text) + " " * (w - len(text)))
            print(ink.dim(" │ ").join(parts).rstrip())

    # -- cell contents ----------------------------------------------------- #
    def _task_cell(self, ex, ref, width):
        out = []
        for para in ex.prompt.split("\n"):
            out += [(l, None) for l in textwrap.wrap(para, width) or [""]]
        budget = f"budget: {ref.nqueries} quer{'y' if ref.nqueries == 1 else 'ies'}"
        out += [("", None), (budget, self.ink.yellow)]
        if ex.mutates:
            out.append(("(writes are rolled back)", self.ink.dim))
        return out

    def _sql_lines(self, att, width, limit=4):
        """The SQL the attempt actually ran, one line per distinct query shape."""
        if not att.queries:
            return []
        dim = self.ink.dim
        shapes = att.shapes()
        plural = "query" if len(att.queries) == 1 else "queries"
        head = f"sql - {len(att.queries)} {plural}"
        if len(shapes) != len(att.queries):
            head += f", {len(shapes)} distinct"
        out = [("", None), (head + ":", dim)]
        for i, (sql, n) in enumerate(shapes[:limit], 1):
            repeat = f"x{n} " if n > 1 else ""
            out.append((f"{i}. {repeat}{engine.shorten_sql(sql)}", dim))
        if len(shapes) > limit:
            out.append((f"... {len(shapes) - limit} more shape(s)", dim))
        out.append((":v sql for the full text", dim))
        return out

    def _result_budget(self):
        """(rows, sql shapes) that still leave the screen readable."""
        lines = shutil.get_terminal_size((80, 24)).lines
        return min(14, max(4, lines - 24)), min(5, max(2, (lines - 18) // 4))

    def _result_cell(self, ex, grade, width, max_rows=14, max_sql=4):
        ink, att = self.ink, grade.attempt
        out = [(f">>> {line}", ink.dim) for line in att.code.split("\n")[:4]]
        plural = "query" if grade.nqueries == 1 else "queries"
        if att.shape_error:
            out += [("✗ the grader cannot read what you returned", ink.red),
                    (f"you returned {att.raw}", ink.dim),
                    (att.error.split("\n")[-1], None)]
            return out + self._sql_lines(att, width, max_sql)
        if att.error:
            out.append(("✗ your code raised", ink.red))
            out += [(l.strip(), None) for l in att.error.split("\n")[-4:]]
            return out + self._sql_lines(att, width, max_sql)
        if grade.better:
            out.append((f"✓ correct in {grade.nqueries} {plural} - beats the "
                        f"reference ({grade.target})!", ink.green))
        elif grade.optimal:
            out.append((f"✓ correct, {grade.nqueries} {plural} - optimal", ink.green))
        elif grade.ok:
            out.append((f"~ correct, but {grade.nqueries} {plural} "
                        f"instead of {grade.target}", ink.yellow))
        else:
            out.append((f"✗ wrong answer ({grade.nqueries} {plural})", ink.red))
        if grade.ok and not grade.optimal and att.repeated_shapes():
            out.append(("the repeated query below is the N+1", ink.dim))
        rows, total = engine.render_rows(att.value, width, max_rows)
        out.append(("", None))
        out += [(r, None) for r in rows]
        tail = []
        if total > len(rows):
            tail.append(f"{total} rows in all")
        if not grade.ok:
            ref = self.reference(ex)
            if isinstance(ref.value, list) and isinstance(att.value, list):
                tail.append(f"reference has {len(ref.value)}")
        if total > len(rows) or not grade.ok:
            tail.append(":v to view, :diff to compare" if not grade.ok else ":v to view it all")
        if tail:
            out.append((" - ".join(tail), ink.dim))
        return out + self._sql_lines(att, width, max_sql)

    def _schema_cell(self, ex, contract, width, max_lines=None):
        """Field definitions, capped so the whole screen still fits the window."""
        if max_lines is None:
            max_lines = max(12, shutil.get_terminal_size((80, 24)).lines - 12)
        out = []
        for line in schema.panel(ex, contract, width=width, max_lines=max_lines):
            out.append((line, self.ink.bold if line and not line.startswith(" ") else self.ink.dim))
        return out

    # -- the exercise screen ----------------------------------------------- #
    def show(self, ex):
        self.paint(ex, None)

    def paint(self, ex, grade):
        ink, ref = self.ink, self.reference(ex)
        contract = engine.source_of(ex.consume)
        plan, width = self._plan(grade is not None)
        done = self.data["exercises"].get(ex.slug, {})
        badge = ""
        if done.get("solved") and grade is None:
            best, target = done.get("best_queries"), done.get("target")
            ok = best is not None and target is not None and best <= target
            badge = ink.dim(f"  [{'solved' if ok else 'solved (slow)'}, best {best}q]")
        rule = min(width - 1, sum(w for _n, w in plan) + 3 * (len(plan) - 1)) if plan \
            else min(width - 1, 78)

        print()
        if self.show_keys:
            for line in self._keybar(max(rule, 60)):
                print(ink.dim(line))
        print(ink.blue("─" * rule))
        title = ink.dim(f"   {ex.title}") if self.revealed(ex) else ""
        print(ink.bold(f"Exercise #{ex.number}") +
              ink.dim(f" of {len(EXERCISES)}   [{ex.section}]") + title + badge)
        print(ink.blue("─" * rule))

        if plan:
            names = [n for n, _w in plan]
            cells = {}
            for name, w in plan:
                if name == "task":
                    cells[name] = self._task_cell(ex, ref, w)
                elif name == "schema":
                    cells[name] = self._schema_cell(ex, contract, w)
                else:
                    cells[name] = self._result_cell(ex, grade, w, *self._result_budget())
            self._grid(cells, plan)
            if grade is not None and "task" not in names:
                pass          # the task is a few lines up in the scrollback
        else:
            if self.show_schema and grade is None:
                for line in schema.compact(ex, contract, width=min(width, 96) - 4):
                    print(ink.dim("  " + line))
                print()
            if grade is None:
                for para in ex.prompt.split("\n"):
                    for line in textwrap.wrap(para, min(width, 98) - 2, initial_indent="  ",
                                              subsequent_indent="  ") or [""]:
                        print(line)
                print()
                print(ink.yellow(f"  budget: {ref.nqueries} "
                                 f"quer{'y' if ref.nqueries == 1 else 'ies'}" +
                                 ("   (writes are rolled back)" if ex.mutates else "")))
            else:
                cell_w = min(width, 112) - 3
                rows, sqls = self._result_budget()
                for text, style in self._result_cell(ex, grade, cell_w, rows, sqls):
                    line = ("  " + self._clip(text, cell_w)).rstrip()
                    print(style(line) if style else line)

        if contract and (grade is None or grade.attempt.shape_error):
            print()
            print(ink.dim("  the grader consumes your result like this:"))
            for line in contract.split("\n"):
                print(ink.dim("    " + line))
        if grade is None and ex.hints:
            print(ink.dim(f"  {len(ex.hints)} hint(s) available - :hint"))
        if grade is not None and (grade.optimal or grade.better):
            self.compare(ex, grade)
        if grade is not None and ex.notes and (grade.optimal or grade.better):
            print()
            print(ink.dim("  " + ex.notes.replace("\n", "\n  ")))
        if grade is not None and not (grade.optimal or grade.better):
            print(ink.dim("  try again, :hint, or :s for the solution"))

    @staticmethod
    def _same_code(a, b):
        strip = lambda t: re.sub(r"\s+", "", t).replace('"', "'")  # noqa: E731
        return strip(a) == strip(b)

    def compare(self, ex, grade):
        """Once it passes, put your answer next to the reference one."""
        ink = self.ink
        mine, ref = grade.attempt.code.strip(), ex.solution.strip()
        print()
        if self._same_code(mine, ref):
            print(ink.dim(f"  that is the reference solution - {ex.title}"))
            return
        print(ink.dim(f"  reference solution ({ex.title}), {grade.target} "
                      f"quer{'y' if grade.target == 1 else 'ies'}:"))
        for line in ref.split("\n"):
            print(ink.green("    " + line))
        print(ink.dim(f"  yours, {grade.nqueries} quer"
                      f"{'y' if grade.nqueries == 1 else 'ies'}"
                      f"{' - fewer!' if grade.better else ''}:"))
        for line in mine.split("\n"):
            print("    " + line)

    def solution(self, ex):
        ink, ref = self.ink, self.reference(ex)
        progress.mark_shown(self.data, ex)
        print(ink.bold(f"  reference solution - {ex.title}:"))
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

    def view(self, ex, what=None):
        """Full-screen preview of a long answer - the pager exits on q."""
        what = (what or "mine").lower()
        if what in ("ref", "reference", "solution"):
            ref = self.reference(ex)
            pager.page(engine.dumps(ref.value),
                       f"reference answer - Exercise #{ex.number} {ex.title} "
                       f"({ref.nqueries} queries)")
        elif what == "sql":
            if self.last is None:
                print("  nothing run yet")
                return
            body = "\n\n".join(f"{i:>3}. [{q['time']}s] {q['sql']}"
                                for i, q in enumerate(self.last.queries, 1))
            pager.page(body or "no queries at all",
                       f"exact SQL - {len(self.last.queries)} "
                       f"quer{'y' if len(self.last.queries) == 1 else 'ies'} "
                       f"from your last attempt")
        elif self.last is None or self.last.error:
            print("  no result to view - run a query first")
        else:
            pager.page(engine.dumps(self.last.value),
                       f"your last answer - {self.label(ex)} "
                       f"({self.last.nqueries} queries)")

    def listing(self, titles=False):
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
            name = ex.title if (titles or self.revealed(ex)) else ""
            print(f"{flag} {ex.number:>3}. {name}".rstrip())

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
            print(self.ink.dim(f"  {i:>3}. {q['time']}s  ")
                  + engine._trim(engine.shorten_sql(q["sql"]), 140))
        hidden = len(self.last.queries) - shown
        if hidden:
            print(self.ink.dim(f"  ... {hidden} more query/queries not shown; "
                               f"{len(self.last.shape_counts())} distinct shape(s) in total:"))
            for n, shape in self.last.repeated_shapes()[:3]:
                print(self.ink.dim(f"      {n}x  ")
                      + engine._trim(engine.shorten_sql(shape), 100))
        print(self.ink.dim("  (names shortened; :v sql has the exact text)"))

    def data_summary(self):
        from practice import seed  # noqa: F401
        from django.apps import apps
        for model in sorted(apps.get_app_config("bookstore").get_models(), key=lambda m: m.__name__):
            print(f"  {model.__name__:<16} {model.objects.count():>6}")

    def models(self):
        ink = self.ink
        for line in schema.full():
            print(ink.bold("  " + line) if line and not line.startswith(" ") else ink.dim("  " + line))

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
            self.paint(current, grade)
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

    @staticmethod
    def _complete_expression(source):
        """True when the buffer is already a full expression - nothing more to wait for."""
        import ast
        try:
            ast.parse(source, mode="eval")
            return True
        except SyntaxError:
            return False

    def read(self):
        """Read one snippet.

        A complete expression runs as soon as you hit enter. Anything else - an
        assignment, a loop, several statements - keeps reading until a blank line,
        because the whole snippet has to be measured as one unit.
        """
        lines, forced = [], False
        if self.pending is not None:
            pending, self.pending = self.pending, None
            if pending.startswith(":") or pending in ("?", "help"):
                return pending
            if self._complete_expression(pending):
                return pending
            lines.append(pending)
        while True:
            if lines and not self.told_multiline:
                self.told_multiline = True
                print(self.ink.dim("    (writing a snippet - type it like a file, dedent to close "
                                   "a block; a blank line runs it)"))
            line = input(self.ink.rl("36", ">>> " if not (lines or forced) else "... "))
            if not lines and line.strip() in (":multi", ":ml"):
                forced = self.told_multiline = True
                print(self.ink.dim("    (multi-statement snippet: blank line runs it)"))
                continue
            if not lines and (line.strip().startswith(":") or line.strip() in ("?", "help")):
                return line.strip()
            if (lines or forced) and not line.strip():
                return "\n".join(lines)
            if line.rstrip().endswith("\\"):        # explicit continuation
                forced = True
                line = line.rstrip()[:-1]
            lines.append(line)
            source = "\n".join(lines)
            if not source.strip():
                return None
            if not forced and self._complete_expression(source):
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
            self.listing(titles=arg in ("all", "titles"))
        elif cmd == "sql":
            self.sql()
        elif cmd in ("v", "view"):
            self.view(ex, arg)
        elif cmd in ("keys", "k"):
            self.show_keys = not self.show_keys
            self.data["keys"] = self.show_keys
            progress.save(self.data)
            print(f"  shortcut bar {'on' if self.show_keys else 'off'}")
            self.paint(ex, self.last_grade)
        elif cmd in ("lay", "layout"):
            order = ["auto", "3", "2", "stack"]
            self.layout = order[(order.index(self.layout) + 1) % len(order)] \
                if arg is None else (arg if arg in order else self.layout)
            self.data["layout"] = self.layout
            progress.save(self.data)
            print(f"  layout: {self.layout}")
            self.paint(ex, self.last_grade)
        elif cmd == "diff":
            self.diff(ex)
        elif cmd in ("d", "data"):
            self.data_summary()
        elif cmd in ("m", "models"):
            self.models()
        elif cmd == "stats":
            self.stats()
        elif cmd in ("sc", "schema"):
            self.show_schema = not self.show_schema
            self.data["schema"] = self.show_schema
            progress.save(self.data)
            print(f"  schema reminder {'on' if self.show_schema else 'off'}")
            self.show(ex)
        elif cmd == "reset":
            progress.reset()
            self.data = progress.load()
            print("  progress wiped")
        elif cmd in ("r", "repeat", "show"):
            self.show(ex)
        else:
            print(f"  unknown command {raw!r} - :h for the list")
        return None
