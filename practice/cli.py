"""The REPL: show a task, read a query, grade it, repeat."""

import atexit
import collections
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
  :fs            fullscreen on/off (off = screens scroll past each other)
  alt+up/down    step back and forth through the screens of this session
  :b :back       same as alt+up          :f :fwd       same as alt+down
  :key           show what a key combination sends, to bind it yourself
  :stats         your progress            :reset        wipe saved progress
  :q :quit       leave (progress is saved after every attempt)
"""


Frame = collections.namedtuple("Frame", "number lines")

KEYS = [
    (":h", "help"), (":s", "solution"), (":hint", ""), (":v", "view all (q exits)"),
    (":diff", ""), (":sql", ""), (":n", "next"), (":p", "prev"), (":g N", "goto"),
    (":l", "list"), (":m", "models"), (":sc", "schema"), (":lay", "layout"),
    (":ml", "multi-line (blank line runs)"), (":stats", ""), (":q", "quit"),
    ("alt+up/down", "past screens"),
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
        self.fullscreen = self.data.get("fullscreen", True)
        self.frames = []          # every screen drawn this session
        self.frame_at = None      # None = looking at the latest one
        self.current = None

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
    def _soft(text, width, indent="  ", hang=None):
        """Wrap prose or code to the window - an over-wide line breaks fullscreen."""
        hang = indent + "  " if hang is None else hang
        return textwrap.wrap(text, max(20, width - len(hang)), initial_indent=indent,
                             subsequent_indent=hang) or [indent.rstrip()]

    @staticmethod
    def _clip(text, width):
        text = text.rstrip()
        return text if len(text) <= width else text[: width - 1] + "…"

    def _grid(self, cells, plan):
        """cells: {column name: [(text, style), ...]} clipped into place."""
        ink, out = self.ink, []
        height = max((len(cells.get(name, [])) for name, _w in plan), default=0)
        for i in range(height):
            parts = []
            for name, w in plan:
                text, style = (cells.get(name, []) + [("", None)] * height)[i]
                text = self._clip(text, w)
                parts.append((style(text) if style else text) + " " * (w - len(text)))
            out.append(ink.dim(" │ ").join(parts).rstrip())
        return out

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

    def _sql_lines(self, att, width, room=10):
        """The SQL the attempt ran: one clause per line, inside `room` lines."""
        if not att.queries or room < 4:
            return []
        dim = self.ink.dim
        shapes = att.shapes()
        plural = "query" if len(att.queries) == 1 else "queries"
        head = f"sql - {len(att.queries)} {plural}"
        if len(shapes) != len(att.queries):
            head += f", {len(shapes)} distinct"
        out = [("", None), (head + ":", dim)]
        budget, shown = room - 3, 0          # the blank, the header, the footer
        left = len(shapes)
        for i, (sql, repeats) in enumerate(shapes, 1):
            if budget < 2:
                break
            prefix = f"{i}. " + (f"x{repeats} " if repeats > 1 else "")
            lines = engine.wrap_sql(engine.shorten_sql(sql), width, prefix=prefix)
            lines = engine.pick_clauses(lines, max(2, budget // left))
            out += [(line, dim) for line in lines]
            budget -= len(lines)
            left -= 1
            shown += 1
        if shown < len(shapes):
            out.append((f"... {len(shapes) - shown} more, :v sql for all", dim))
        else:
            out.append((":v sql for the exact text", dim))
        return out

    def _result_cell(self, ex, grade, width, room=24):
        """Your query, the verdict, the rows, and the SQL - inside `room` lines.

        The SQL is sized first and the rows take what is left: a row you cannot see
        is a smaller loss than the query that explains the count.
        """
        ink, att = self.ink, grade.attempt
        sql = self._sql_lines(att, width, max(4, min(room - 8, 18)))
        out = [(f">>> {line}", ink.dim) for line in att.code.split("\n")[:3]]
        plural = "query" if grade.nqueries == 1 else "queries"

        if att.shape_error:
            out += [("✗ the grader cannot read what you returned", ink.red),
                    (f"you returned {att.raw}", ink.dim),
                    (att.error.split("\n")[-1], None)]
            return out + sql
        if att.error:
            out.append(("✗ your code raised", ink.red))
            keep = max(1, room - len(out) - len(sql) - 1)
            out += [(line.strip(), None) for line in att.error.split("\n")[-keep:]]
            return out + sql

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

        for_rows = max(2, room - len(out) - len(sql) - 2)
        rows, total = engine.render_rows(att.value, width, for_rows)
        out.append(("", None))
        out += [(row, None) for row in rows]
        tail = []
        if total > len(rows):
            tail.append(f"{total} rows in all")
        if not grade.ok:
            reference = self.reference(ex)
            if isinstance(reference.value, list) and isinstance(att.value, list):
                tail.append(f"reference has {len(reference.value)}")
        if total > len(rows) or not grade.ok:
            tail.append(":v to view, :diff to compare" if not grade.ok else ":v to view it all")
        if tail:
            out.append((" - ".join(tail), ink.dim))
        return out + sql

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
        """Build this screen, keep it for later, draw it."""
        lines = self.build_frame(ex, grade)
        self.frames.append(Frame(ex.number, lines))
        self.frame_at = None
        self.render(lines)

    def render(self, lines, note=None):
        """Draw a screen. In fullscreen mode it replaces what is on display."""
        ink = self.ink
        height = shutil.get_terminal_size((80, 24)).lines
        room = max(8, height - (4 if note else 3))
        if self.fullscreen:
            sys.stdout.write("\033[H\033[2J")
        for line in lines[:room]:
            print(line)
        hidden = len(lines) - len(lines[:room])
        if hidden:
            print(ink.dim(f"  ... {hidden} line(s) did not fit - :v for the answer, "
                          f":m for the schema"))
        if note:
            print(ink.dim(note))

    def build_frame(self, ex, grade):
        """Lay out one screen, sized so that it fits the window without scrolling."""
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

        head = []
        if self.show_keys:
            head += [ink.dim(line) for line in self._keybar(max(rule, 60))]
        title = ink.dim(f"   {ex.title}") if self.revealed(ex) else ""
        head += [
            ink.blue("─" * rule),
            ink.bold(f"Exercise #{ex.number}") +
            ink.dim(f" of {len(EXERCISES)}   [{ex.section}]") + title + badge,
            ink.blue("─" * rule),
        ]

        # everything below the columns, built first so its height is known
        tail = []
        if contract and (grade is None or grade.attempt.shape_error):
            tail.append("")
            tail.append(ink.dim("  the grader consumes your result like this:"))
            for line in contract.split("\n"):
                tail += [ink.dim(part) for part in self._soft(line, width, "    ", "      ")]
        if grade is None and ex.hints:
            tail.append(ink.dim(f"  {len(ex.hints)} hint(s) available - :hint"))
        if grade is not None and (grade.optimal or grade.better):
            tail += self.compare(ex, grade, width)
            if ex.notes:
                tail.append("")
                tail += [ink.dim(part)
                         for part in self._soft(" ".join(ex.notes.split()), width)]
        if grade is not None and not (grade.optimal or grade.better):
            tail.append(ink.dim("  try again, :hint, or :s for the solution"))

        height = shutil.get_terminal_size((80, 24)).lines
        body_room = max(6, height - 3 - len(head) - len(tail))

        if plan:
            cells = {}
            for name, w in plan:
                if name == "task":
                    cell = self._task_cell(ex, ref, w)
                elif name == "schema":
                    cell = self._schema_cell(ex, contract, w, max_lines=body_room)
                else:
                    cell = self._result_cell(ex, grade, w, body_room)
                if len(cell) > body_room:
                    cell = cell[:body_room - 1] + [("... :v / :m for the rest", ink.dim)]
                cells[name] = cell
            body = self._grid(cells, plan)
        else:
            body = []
            if self.show_schema and grade is None:
                body += [ink.dim("  " + line) for line in
                         schema.compact(ex, contract, width=min(width, 96) - 4)]
                body.append("")
            if grade is None:
                for para in ex.prompt.split("\n"):
                    body += textwrap.wrap(para, min(width, 98) - 2, initial_indent="  ",
                                          subsequent_indent="  ") or [""]
                body.append("")
                body.append(ink.yellow(f"  budget: {ref.nqueries} "
                                       f"quer{'y' if ref.nqueries == 1 else 'ies'}" +
                                       ("   (writes are rolled back)" if ex.mutates else "")))
            else:
                cell_w = min(width, 112) - 3
                for text, style in self._result_cell(ex, grade, cell_w, body_room):
                    line = ("  " + self._clip(text, cell_w)).rstrip()
                    body.append(style(line) if style else line)
            body = body[:body_room]
        return head + body + tail

    # -- moving through the screens of this session ------------------------- #
    def browse(self, delta):
        if not self.frames:
            return
        at = len(self.frames) - 1 if self.frame_at is None else self.frame_at
        target = at + delta
        if target < 0:
            print(self.ink.dim("  that is the oldest screen of this session"))
            return
        target = min(target, len(self.frames) - 1)
        self.frame_at = None if target == len(self.frames) - 1 else target
        frame = self.frames[target]
        ex = get(frame.number)
        if ex is not None and ex is not self.current:
            self.current = ex
            self.hint_at = 0
            progress.set_current(self.data, ex.number)
        where = f"screen {target + 1}/{len(self.frames)}"
        if self.frame_at is None:
            where += " (latest)"
        self.render(frame.lines,
                    note=f"  {where}   alt+up / alt+down to move   "
                         f"the prompt belongs to Exercise #{self.current.number}")

    def bind_keys(self):
        """Wire alt/ctrl + up/down to the screen history.

        readline owns the line, so the binding is a macro that clears whatever is
        typed and submits ':back'/':fwd' - the same thing you could type by hand.
        """
        sequences = {
            ":back": (r"\e[1;3A", r"\e\e[A", r"\e[1;5A", r"\e[1;9A", r"\e[1;2A"),
            ":fwd": (r"\e[1;3B", r"\e\e[B", r"\e[1;5B", r"\e[1;9B", r"\e[1;2B"),
        }
        for command, keys in sequences.items():
            for key in keys:
                try:
                    readline.parse_and_bind(f'"{key}": "\\C-a\\C-k{command}\\n"')
                except Exception:          # libedit, or a readline build that refuses
                    return

    def probe_key(self):
        """Report what a key combination actually sends, so it can be bound."""
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            print("  needs a real terminal")
            return
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        print(self.ink.dim("  press the key combination ... "), end="", flush=True)
        try:
            tty.setraw(fd)
            data = os.read(fd, 8)
            while select.select([fd], [], [], 0.06)[0]:
                data += os.read(fd, 8)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        shown = data.decode(errors="replace").replace("\033", r"\e")
        print(f'\n  it sends "{shown}"')
        print(self.ink.dim("  to use it for screen history, put this in ~/.inputrc:"))
        print(f'    "{shown}": "\\C-a\\C-k:back\\n"')

    @staticmethod
    def _same_code(a, b):
        strip = lambda t: re.sub(r"\s+", "", t).replace('"', "'")  # noqa: E731
        return strip(a) == strip(b)

    def compare(self, ex, grade, width=96):
        """Once it passes, put your answer next to the reference one."""
        ink = self.ink
        mine, ref = grade.attempt.code.strip(), ex.solution.strip()
        out = [""]
        if self._same_code(mine, ref):
            return out + [ink.dim(part) for part in
                          self._soft(f"that is the reference solution - {ex.title}", width)]
        out += [ink.dim(part) for part in
                self._soft(f"reference solution ({ex.title}), {grade.target} "
                           f"quer{'y' if grade.target == 1 else 'ies'}:", width)]
        for line in ref.split("\n"):
            out += [ink.green(part) for part in self._soft(line, width, "    ", "      ")]
        out += [ink.dim(part) for part in
                self._soft(f"yours, {grade.nqueries} quer"
                           f"{'y' if grade.nqueries == 1 else 'ies'}"
                           f"{' - fewer!' if grade.better else ''}:", width)]
        for line in mine.split("\n"):
            out += self._soft(line, width, "    ", "      ")
        return out

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
        width = min(shutil.get_terminal_size((80, 24)).columns, 120) - 4
        for i, (sql, repeats) in enumerate(self.last.shapes()[:limit], 1):
            prefix = f"{i}. " + (f"x{repeats} " if repeats > 1 else "")
            for line in engine.wrap_sql(engine.shorten_sql(sql), width, prefix=prefix):
                print(self.ink.dim("  " + line))
        extra = len(self.last.shapes()) - limit
        if extra > 0:
            print(self.ink.dim(f"  ... {extra} more shape(s)"))
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
        self.bind_keys()

        ink = self.ink
        print(ink.bold("django ORM practice") +
              ink.dim(f"   {len(EXERCISES)} exercises, in-memory sqlite, "
                      f"all models pre-imported"))
        self.current = get(self.number) or EXERCISES[0]
        self.hint_at = 0
        self.show(self.current)
        while True:
            try:
                code = self.read()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if code is None:
                continue
            if code.startswith(":") or code in ("?", "help"):
                nxt = self.command(code, self.current)
                if nxt == "quit":
                    break
                if isinstance(nxt, int):
                    target = get(nxt)
                    if target is None:
                        print(f"  no exercise {nxt}")
                        continue
                    self.current = target
                    self.hint_at, self.last = 0, None
                    progress.set_current(self.data, self.current.number)
                    self.show(self.current)
                continue
            grade = engine.grade(self.current, code, self.reference(self.current))
            self.last, self.last_grade = grade.attempt, grade
            progress.record_attempt(self.data, self.current, grade)
            self.paint(self.current, grade)
            if grade.ok and self.only is None:
                nxt = get(self.current.number + 1)
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
                self.current = nxt
                self.hint_at, self.last = 0, None
                progress.set_current(self.data, self.current.number)
                self.show(self.current)
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
        elif cmd in ("back", "b"):
            self.browse(-1)
        elif cmd in ("fwd", "forward", "f"):
            self.browse(+1)
        elif cmd == "key":
            self.probe_key()
        elif cmd in ("fs", "fullscreen"):
            self.fullscreen = not self.fullscreen
            self.data["fullscreen"] = self.fullscreen
            progress.save(self.data)
            print(f"  fullscreen {'on' if self.fullscreen else 'off'}")
            self.paint(ex, self.last_grade)
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
