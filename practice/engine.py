"""Run a user's ORM snippet, count the queries it really costs, and grade it."""

import ast
import collections
import datetime
import linecache
import sys
import decimal
import json
import re
import textwrap
import traceback
from dataclasses import dataclass, field

from django.db import connection, models, transaction
from django.test.utils import CaptureQueriesContext

def shape_of(sql):
    """The query with its literals blanked out, so N+1 repeats collapse together."""
    return re.sub(r"'[^']*'", "?", re.sub(r"\b\d+\b", "?", sql))


def _split_top_level(text, separator=","):
    """Split on `separator`, ignoring anything inside parentheses."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == separator and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def _collapse_columns(sql, budget):
    """SELECT a, b, c, d FROM x -> SELECT a, +3 cols FROM x, when it will not fit.

    The column list is the least interesting part of a query and the longest, so it
    is what gives way when the JOIN and the WHERE would otherwise be pushed out of
    sight - but only then: within `budget` characters the columns stay.
    """
    head = re.match(r"SELECT\s+(DISTINCT\s+)?", sql, re.I)
    if not head:
        return sql
    depth, cut = 0, None
    for m in re.finditer(r"[()]|\sFROM\s", sql[head.end():], re.I):
        token = m.group()
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0:
            cut = head.end() + m.start()
            break
    if cut is None:
        return sql
    listing = sql[head.end():cut]
    if len(listing) <= budget:
        return sql
    columns = _split_top_level(listing)
    if len(columns) <= 2:
        return sql
    return f"{sql[:head.end()]}{columns[0].strip()}, +{len(columns) - 1} cols{sql[cut:]}"


def shorten_sql(sql, width=None, lines=2):
    """Drop the quoting and the app prefix - unreadable in a narrow column.

    With a `width`, a column list longer than `lines` lines of it collapses to
    `+N cols`; without one the query is left whole.
    """
    sql = " ".join(re.sub(r"\bbookstore_", "", sql.replace('"', "")).split())
    return _collapse_columns(sql, width * lines) if width else sql


CLAUSES = (
    "SELECT", "FROM", "INNER JOIN", "LEFT OUTER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "CROSS JOIN", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "OFFSET",
    "UNION ALL", "UNION", "INSERT INTO", "UPDATE", "DELETE FROM", "SET", "VALUES",
)


def _is_word_edge(sql, index):
    return index <= 0 or not (sql[index - 1].isalnum() or sql[index - 1] == "_")


def clause_chunks(sql):
    """Break a query at its top-level clauses; subqueries stay in one piece."""
    out, depth, start, i = [], 0, 0, 0
    upper = sql.upper()
    while i < len(sql):
        char = sql[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and _is_word_edge(sql, i):
            for keyword in CLAUSES:
                if not upper.startswith(keyword, i):
                    continue
                after = i + len(keyword)
                if after < len(sql) and (sql[after].isalnum() or sql[after] == "_"):
                    continue
                if i > start:
                    out.append(sql[start:i].strip())
                    start = i
                i = after - 1
                break
        i += 1
    out.append(sql[start:].strip())
    return [chunk for chunk in out if chunk]


def wrap_sql(sql, width, prefix="", indent="   "):
    """One clause per line, wrapped again if a clause is still too wide."""
    lines, deep = [], indent + "  "
    for position, chunk in enumerate(clause_chunks(sql)):
        lead = prefix if position == 0 else indent
        room = max(20, width - max(len(lead), len(deep)))
        pieces = textwrap.wrap(chunk, room) or [""]
        lines.append(lead + pieces[0])
        lines += [deep + piece for piece in pieces[1:]]
    return lines


CLAUSE_WORTH = (
    ("WHERE", 0), ("INNER JOIN", 1), ("LEFT", 1), ("RIGHT", 1), ("CROSS", 1),
    ("FROM", 2), ("GROUP BY", 3), ("HAVING", 3), ("ORDER BY", 4), ("LIMIT", 5),
    ("OFFSET", 5),
)


def pick_clauses(lines, keep):
    """Trim a wrapped query to `keep` lines, dropping the least telling clauses.

    ORDER BY and LIMIT go first; WHERE and the JOINs are what explain a query
    count, so they stay. The first line stays because it carries the xN marker.
    """
    if len(lines) <= keep:
        return lines
    scored = []
    for index, line in enumerate(lines):
        text = line.strip().upper()
        worth = -1 if index == 0 else next(
            (w for keyword, w in CLAUSE_WORTH if text.startswith(keyword)), 3)
        scored.append((worth, index, line))
    chosen = sorted(sorted(scored)[:keep], key=lambda item: item[1])
    out = [line for _worth, _index, line in chosen]
    return out[:-1] + [out[-1] + " ..."]


ANSWER = "<answer>"          # the filename your snippet is compiled under

TXN_NOISE = re.compile(r"^\s*(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.I)


class UserInputError(Exception):
    """Not a bug in the snippet's SQL - the snippet itself is unusable."""


class _Rollback(Exception):
    """Raised to unwind the atomic block so every attempt leaves the DB pristine."""


def build_namespace():
    """Everything a solution might reasonably reach for, pre-imported."""
    import datetime as _dt
    from decimal import Decimal

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import functions as dbfunc

    from bookstore import models as m

    ns = {}
    for name in dir(m):
        obj = getattr(m, name)
        if isinstance(obj, type) and issubclass(obj, models.Model):
            ns[name] = obj
    ns["Books"] = m.Book  # the article calls it Books
    ns["ContentType"] = ContentType
    for name in dir(models):
        if not name.startswith("_"):
            ns[name] = getattr(models, name)
    for name in dir(dbfunc):
        if not name.startswith("_"):
            ns.setdefault(name, getattr(dbfunc, name))
    ns.update(
        models=models, connection=connection, Decimal=Decimal, datetime=_dt,
        date=_dt.date, timedelta=_dt.timedelta, __builtins__=__builtins__,
    )
    return ns


# --------------------------------------------------------------------------- #
# normalisation: turn any ORM result into a comparable, printable structure
# --------------------------------------------------------------------------- #

def normalize(value, sort, depth=0):
    n = lambda v: normalize(v, sort, depth + 1)  # noqa: E731
    if isinstance(value, models.Model):
        return f"{type(value).__name__}#{value.pk}"
    if isinstance(value, models.QuerySet):
        return _maybe_sort([n(v) for v in value], sort or depth > 0)
    if isinstance(value, dict):
        return {str(k): n(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (set, frozenset)):
        return sorted((n(v) for v in value), key=_key)
    if isinstance(value, (list, tuple)):
        return _maybe_sort([n(v) for v in value], sort or depth > 0)
    if isinstance(value, decimal.Decimal):
        return round(float(value), 6)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if hasattr(value, "__iter__"):
        return _maybe_sort([n(v) for v in value], sort or depth > 0)
    return str(value)


def _key(v):
    return json.dumps(v, sort_keys=True, default=str)


def _maybe_sort(items, sort):
    return sorted(items, key=_key) if sort else items


def canonical(value, order_matters):
    """Deep-normalise. Top-level order is only preserved when the task demands it."""
    return normalize(value, sort=not order_matters)


# --------------------------------------------------------------------------- #
# execution
# --------------------------------------------------------------------------- #

def _user_line():
    """The last line of the user's own snippet on the current traceback."""
    tb, line = sys.exc_info()[2], None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == ANSWER:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def _user_traceback(exc):
    """The traceback from your snippet down, without this module's frames on top."""
    tb = exc.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename != ANSWER:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(exc), exc, tb or exc.__traceback__))


def _exec_eval(code, ns):
    # let traceback/linecache show the snippet's source instead of a bare line number
    linecache.cache[ANSWER] = (len(code), None, code.splitlines(True), ANSWER)
    tree = ast.parse(code, mode="exec")
    if not tree.body:
        raise UserInputError("Nothing to run.")
    last = tree.body[-1]
    if isinstance(last, ast.Expr):
        if tree.body[:-1]:
            exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), ANSWER, "exec"), ns)
        return eval(compile(ast.Expression(last.value), ANSWER, "eval"), ns)
    exec(compile(tree, ANSWER, "exec"), ns)
    for key in ("answer", "result", "out", "qs"):
        if key in ns:
            return ns[key]
    raise UserInputError(
        "Your snippet ends with a statement, not an expression, and defines no `answer`.\n"
        "Each submission runs on its own (fresh namespace, rolled back afterwards), so send the\n"
        "whole thing at once and finish with the expression to grade - or assign it to `answer`."
    )


@dataclass
class Attempt:
    code: str
    value: object = None
    error: str = None
    queries: list = field(default_factory=list)
    shape_error: bool = False     # the grader could not consume what you returned
    raw: str = None               # what you did return, described cheaply
    error_line: int = None        # which line of *your* snippet raised
    traceback: str = None         # the whole thing, for :v err

    @property
    def nqueries(self):
        return len(self.queries)

    def shape_counts(self):
        shapes = {}
        for q in self.queries:
            shapes.setdefault(shape_of(q["sql"]), []).append(q)
        return shapes

    def shapes(self):
        """[(sql, how many like it)] in the order the shapes first appeared."""
        out, index = [], {}
        for q in self.queries:
            key = shape_of(q["sql"])
            if key in index:
                out[index[key]][1] += 1
            else:
                index[key] = len(out)
                out.append([q["sql"], 1])
        return [(sql, n) for sql, n in out]

    def repeated_shapes(self):
        """Queries that differ only in their literals -> the N+1 signature."""
        counts = {s: len(qs) for s, qs in self.shape_counts().items()}
        return sorted(((n, s) for s, n in counts.items() if n > 1), reverse=True)


def run(code, consume=None, order_matters=False):
    """Execute `code`, consume its result, and report value + queries.

    Everything happens inside a rolled-back atomic block, so exercises may
    freely write to the database without disturbing later exercises.
    """
    ns = build_namespace()
    attempt = Attempt(code=code)
    with CaptureQueriesContext(connection) as ctx:
        try:
            with transaction.atomic():
                result = _exec_eval(code, ns)
                if consume is not None:
                    try:
                        result = consume(result)
                    except Exception:
                        attempt.shape_error = True
                        attempt.raw = describe(result)
                        raise
                attempt.value = canonical(result, order_matters)
                raise _Rollback
        except _Rollback:
            pass
        except UserInputError as exc:
            attempt.error = str(exc)
        except SyntaxError as exc:
            attempt.error = f"SyntaxError: {exc.msg}"
            attempt.error_line = exc.lineno
            attempt.traceback = "".join(
                traceback.format_exception_only(type(exc), exc))
        except Exception as exc:
            attempt.error = f"{type(exc).__name__}: {exc}"
            attempt.error_line = _user_line()
            attempt.traceback = _user_traceback(exc)
    attempt.queries = [q for q in ctx.captured_queries if not TXN_NOISE.match(q["sql"])]
    return attempt


def describe(value):
    """Name what an expression returned without running more queries for it."""
    if isinstance(value, models.QuerySet):
        from django.db.models.query import (
            FlatValuesListIterable, ValuesIterable, ValuesListIterable,
        )
        kind = {
            ValuesIterable: "a .values() QuerySet (dicts, not model instances)",
            ValuesListIterable: "a .values_list() QuerySet (tuples, not model instances)",
            FlatValuesListIterable: "a flat .values_list() QuerySet (bare values)",
        }.get(value._iterable_class)
        return kind or f"a QuerySet of {value.model.__name__}"
    if isinstance(value, models.Model):
        return f"a single {type(value).__name__} instance"
    if isinstance(value, (list, tuple)) and value:
        return f"a {type(value).__name__} of {type(value[0]).__name__}"
    return f"a {type(value).__name__}"


def _short_traceback():
    lines = traceback.format_exc().splitlines()
    keep = [l for i, l in enumerate(lines) if i == 0 or "engine.py" not in l]
    return "\n".join(keep[-8:])


# --------------------------------------------------------------------------- #
# grading
# --------------------------------------------------------------------------- #

@dataclass
class Grade:
    ok: bool                 # right answer?
    optimal: bool            # right answer in <= the reference query count?
    better: bool             # right answer in *fewer* queries than the reference
    nqueries: int
    target: int
    attempt: Attempt

    @property
    def status(self):
        if self.attempt.error:
            return "error"
        if not self.ok:
            return "wrong"
        if self.better:
            return "better"
        return "optimal" if self.optimal else "slow"


def grade(exercise, code, reference):
    attempt = run(code, exercise.consume, exercise.order_matters)
    ok = attempt.error is None and attempt.value == reference.value
    return Grade(
        ok=ok,
        optimal=ok and attempt.nqueries <= reference.nqueries,
        better=ok and attempt.nqueries < reference.nqueries,
        nqueries=attempt.nqueries,
        target=reference.nqueries,
        attempt=attempt,
    )


def preview(value, limit=6, width=100):
    """Short, readable rendering of a normalised value."""
    if isinstance(value, list):
        head = ",\n ".join(_trim(json.dumps(v, default=str), width) for v in value[:limit])
        more = f"\n ... ({len(value)} items total)" if len(value) > limit else ""
        return f"[{head}{more}\n]" if value else "[]  (empty!)"
    return _trim(json.dumps(value, default=str, indent=1), width * 4)


def _shape_name(value):
    if isinstance(value, list):
        return f"a list of {len(value)} row(s)"
    if isinstance(value, dict):
        return f"a dict with {len(value)} key(s)"
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return "a number"
    return "a string" if isinstance(value, str) else type(value).__name__


def _key(value):
    return json.dumps(value, sort_keys=True, default=str)


def diff_report(mine, reference, order_matters=False, limit=3):
    """Why the answer is wrong, in a few lines: what is missing, what is extra.

    Both values are already normalised, so this compares them as multisets - which
    is also how they were graded.
    """
    if isinstance(reference, list) and isinstance(mine, list):
        missing = list((collections.Counter(map(_key, reference))
                        - collections.Counter(map(_key, mine))).elements())
        extra = list((collections.Counter(map(_key, mine))
                      - collections.Counter(map(_key, reference))).elements())
        if not missing and not extra:
            return [f"the same {len(reference)} rows, but in a different order"
                    if order_matters else f"the same {len(reference)} rows"]
        out = [f"you returned {len(mine)} row(s), the reference has {len(reference)}"]
        for label, rows in ((f"missing from yours", missing),
                            ("the reference does not have", extra)):
            if not rows:
                continue
            out.append(f"{len(rows)} row(s) {label}:")
            out += ["  " + row for row in rows[:limit]]
            if len(rows) > limit:
                out.append(f"  ... {len(rows) - limit} more")
        return out
    if isinstance(reference, dict) and isinstance(mine, dict):
        out = []
        absent = [k for k in reference if k not in mine]
        spare = [k for k in mine if k not in reference]
        if absent:
            out.append("missing key(s): " + ", ".join(absent))
        if spare:
            out.append("unexpected key(s): " + ", ".join(spare))
        for key in reference:
            if key in mine and mine[key] != reference[key]:
                out.append(f"{key}: expected {_key(reference[key])}, "
                           f"you have {_key(mine[key])}")
        return out or ["the same keys and values in a different order"]
    if type(mine) is not type(reference):
        return [f"expected {_shape_name(reference)}, you returned {_shape_name(mine)}"]
    return [f"expected:  {_key(reference)}", f"you have:  {_key(mine)}"]


def row_texts(value, limit=60):
    """(one untrimmed string per row, total row count) - the caller wraps them."""
    if isinstance(value, list):
        rows = [json.dumps(v, default=str) for v in value[:limit]]
        return (rows or ["[]  (empty!)"]), len(value)
    if isinstance(value, dict):
        items = list(value.items())[:limit]
        return [f"{k}: {json.dumps(v, default=str)}" for k, v in items], len(value)
    return [json.dumps(value, default=str)], 1


def dumps(value):
    """The whole answer, pretty-printed, for the pager."""
    if isinstance(value, list):
        body = "\n".join(f"{i:>4}. {json.dumps(v, default=str)}" for i, v in enumerate(value, 1))
        return f"{len(value)} row(s)\n\n{body}\n"
    return json.dumps(value, default=str, indent=2, sort_keys=True) + "\n"


def _trim(text, width):
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def source_of(fn):
    """The consume function's source, shown to the user as the output contract."""
    if fn is None:
        return None
    try:
        import inspect

        src = textwrap.dedent(inspect.getsource(fn)).strip()
    except (OSError, TypeError):
        return None
    src = re.sub(r"^consume\s*=\s*", "", src).rstrip(",")
    return src
