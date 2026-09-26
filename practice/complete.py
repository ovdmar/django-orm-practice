"""Tab completion: model names, attributes, and field paths inside strings.

Three contexts, decided from the line readline is holding:

    Auth<TAB>                       -> names in the namespace (models, Q, Count, ...)
    Book.pub<TAB>                   -> attributes of Book, fields included
    ...select_related('pub<TAB>     -> field paths on the model the line named last,
    ...filter(price__<TAB>             walking __ hops and offering lookups at the end
"""

import re

from django.db import models

LOOKUPS = (
    "exact", "iexact", "contains", "icontains", "in", "gt", "gte", "lt", "lte",
    "startswith", "istartswith", "endswith", "iendswith", "range", "isnull",
    "year", "month", "day", "week_day", "date", "regex", "iregex",
)
DOTTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
WORD = re.compile(r"[A-Za-z_]\w*")


def _is_model(obj):
    return isinstance(obj, type) and issubclass(obj, models.Model)


def _model_of(obj):
    """The model behind a class, a manager or a queryset."""
    if _is_model(obj):
        return obj
    model = getattr(obj, "model", None)
    return model if _is_model(model) else None


# what each call will actually accept as its last path segment
CALL_KIND = {
    "select_related": "joinable",        # forward FK/O2O and reverse O2O only
    "prefetch_related": "relation",
    "Prefetch": "relation",
}


def _query_names(model, kind="any"):
    """Names usable in a field path: fields, FK columns, reverse accessors."""
    names = []
    for field in model._meta.get_fields():
        if type(field).__name__ == "GenericForeignKey":
            continue                      # not traversable in a query
        if kind == "relation" and not field.is_relation:
            continue
        if kind == "joinable" and not (field.many_to_one or field.one_to_one):
            continue
        names.append(field.name)
        if kind == "any":
            attname = getattr(field, "attname", None)
            if attname and attname != field.name:
                names.append(attname)
    return names


def _enclosing_call(before):
    """The function whose parentheses the cursor sits inside."""
    depth = 0
    for index in range(len(before) - 1, -1, -1):
        char = before[index]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                match = re.search(r"([A-Za-z_]\w*)\s*$", before[:index])
                return match.group(1) if match else None
            depth -= 1
    return None


def _step(model, name):
    """Follow one __ hop, or None if `name` is not a relation on `model`."""
    for field in model._meta.get_fields():
        if name in (field.name, getattr(field, "attname", None)):
            return field.related_model if field.is_relation else None
    return None


def _has_field(model, name):
    return any(name in (f.name, getattr(f, "attname", None))
               for f in model._meta.get_fields())


class Completer:
    """readline completer. `line_reader` returns (line buffer, start of the word)."""

    def __init__(self, namespace, line_reader=None):
        self.namespace = namespace
        self.matches = []
        if line_reader is None:
            import readline

            line_reader = lambda: (readline.get_line_buffer(), readline.get_begidx())  # noqa: E731
        self.line_reader = line_reader

    def __call__(self, text, state):
        if state == 0:
            try:
                self.matches = self.collect(text)
            except Exception:
                self.matches = []         # a completer that raises just goes quiet
        return self.matches[state] if state < len(self.matches) else None

    # -- contexts ---------------------------------------------------------- #
    def collect(self, text):
        line, begin = self.line_reader()
        before = line[:begin]
        if self._in_string(line, begin):
            return self.field_paths(text, before)
        if "." in text:
            return self.attributes(text)
        if before.count("(") > before.count(")"):
            # inside a call, so it may be a keyword field path: filter(price__gte=...)
            paths = self.field_paths(text, before)
            if paths:
                return paths
        return self.names(text)

    @staticmethod
    def _in_string(line, begin):
        before = line[:begin]
        return (before.count("'") + before.count('"')) % 2 == 1

    def names(self, text):
        return sorted(name for name in self.namespace
                      if name.startswith(text) and not name.startswith("_"))

    def attributes(self, text):
        head, _, tail = text.rpartition(".")
        if not DOTTED.match(head):
            return []
        obj = eval(head, dict(self.namespace))      # dotted names only, never a call
        names = {name for name in dir(obj) if not name.startswith("_")}
        model = _model_of(obj)
        if model is not None:
            names |= set(_query_names(model))
        return sorted(f"{head}.{name}" for name in names if name.startswith(tail))

    def field_paths(self, text, before):
        """Complete a field path against the last model named before the cursor."""
        model = None
        for word in WORD.findall(before):
            candidate = self.namespace.get(word)
            if _is_model(candidate):
                model = candidate
        if model is None:
            return []
        *hops, prefix = text.split("__")
        for index, hop in enumerate(hops):
            nxt = _step(model, hop)
            if nxt is None:
                if _has_field(model, hop) and index == len(hops) - 1:
                    base = "__".join(hops)
                    return [f"{base}__{lookup}" for lookup in LOOKUPS
                            if lookup.startswith(prefix)]
                return []
            model = nxt
        base = "__".join(hops)
        kind = CALL_KIND.get(_enclosing_call(before), "any")
        return sorted({(f"{base}__{name}" if base else name)
                       for name in _query_names(model, kind) if name.startswith(prefix)})
