"""Run a user's ORM snippet, count the queries it really costs, and grade it."""

import ast
import datetime
import decimal
import json
import re
import textwrap
import traceback
from dataclasses import dataclass, field

from django.db import connection, models, transaction
from django.test.utils import CaptureQueriesContext

TXN_NOISE = re.compile(r"^\s*(BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.I)


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

def _exec_eval(code, ns):
    tree = ast.parse(code, mode="exec")
    if not tree.body:
        raise ValueError("Nothing to run.")
    last = tree.body[-1]
    if isinstance(last, ast.Expr):
        if tree.body[:-1]:
            exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), "<answer>", "exec"), ns)
        return eval(compile(ast.Expression(last.value), "<answer>", "eval"), ns)
    exec(compile(tree, "<answer>", "exec"), ns)
    for key in ("answer", "result", "out", "qs"):
        if key in ns:
            return ns[key]
    raise ValueError(
        "Your snippet ends with a statement, not an expression.\n"
        "Finish with the expression to grade, or assign it to `answer`."
    )


@dataclass
class Attempt:
    code: str
    value: object = None
    error: str = None
    queries: list = field(default_factory=list)
    shape_error: bool = False     # the grader could not consume what you returned
    raw: str = None               # what you did return, described cheaply

    @property
    def nqueries(self):
        return len(self.queries)

    def shape_counts(self):
        shapes = {}
        for q in self.queries:
            shape = re.sub(r"'[^']*'", "?", re.sub(r"\b\d+\b", "?", q["sql"]))
            shapes.setdefault(shape, []).append(q)
        return shapes

    def repeated_shapes(self):
        """Queries that differ only in their literals -> the N+1 signature."""
        shapes = {}
        for q in self.queries:
            shape = re.sub(r"'[^']*'", "?", re.sub(r"\b\d+\b", "?", q["sql"]))
            shapes[shape] = shapes.get(shape, 0) + 1
        return sorted(((n, s) for s, n in shapes.items() if n > 1), reverse=True)


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
        except Exception:
            attempt.error = _short_traceback()
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
