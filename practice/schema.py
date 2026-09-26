"""A compact schema reminder, narrowed down to the models an exercise touches."""

import ast
import collections
import inspect
import re
import textwrap

Rel = collections.namedtuple("Rel", "target arrow reverse")

FORWARD = {"ForeignKey": "->", "OneToOneField": "->1", "ManyToManyField": "<->"}

SHORT = {
    "AutoField": "Auto", "CharField": "Char", "IntegerField": "Int",
    "PositiveIntegerField": "PosInt", "DateField": "Date", "DateTimeField": "DateTime",
    "TextField": "Text", "BooleanField": "Bool", "DecimalField": "Decimal",
    "FloatField": "Float",
}


def _type_label(field, short=False):
    """'CharField(100)?' - the field as the model declares it."""
    name = type(field).__name__
    if short:
        name = SHORT.get(name, name.removesuffix("Field"))
    if getattr(field, "primary_key", False):
        name += "(pk)"
    elif getattr(field, "max_length", None):
        name += f"({field.max_length})"
    if getattr(field, "null", False):
        name += "?"
    return name


def _models():
    from django.apps import apps

    return {m.__name__: m for m in apps.get_app_config("bookstore").get_models()}


def _relations(model):
    """{accessor name: Rel(target, arrow, reverse accessor)} for every relation."""
    out = {}
    for f in model._meta.get_fields():
        if not f.is_relation:
            continue
        if type(f).__name__ == "GenericForeignKey":
            out[f.name] = Rel(None, "-> any model", None)
            continue
        if f.related_model is None:
            continue
        target = f.related_model.__name__
        if f.concrete:
            arrow = FORWARD.get(type(f).__name__, "->")
            null = "?" if getattr(f, "null", False) else ""
            try:                    # what this relation is called from the far side
                back = f.remote_field.get_accessor_name()
            except AttributeError:
                back = None
            out[f.name] = Rel(f.related_model, f"{arrow} {target}{null}", back)
        elif type(f).__name__ == "GenericRelation":
            out[f.name] = Rel(f.related_model, f"<-> {target} (generic)", None)
        else:
            name = f.get_accessor_name()
            if name is None:
                continue
            kind = {"OneToOneRel": "<-1", "ManyToManyRel": "<->"}.get(type(f).__name__, "<-")
            via = f"{target}.{f.remote_field.name}" if kind == "<-" else target
            out[name] = Rel(f.related_model, f"{kind} {via}", None)
    return out


def _str_expr(model):
    """What __str__ returns, with self renamed to o.

    Worth knowing before you count queries: str(obj) is ordinary Python, so one that
    reads a related object costs a query per row, while one that reads book_id does not.
    """
    if "__str__" not in model.__dict__:
        return None
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(model.__str__)))
    except (OSError, TypeError, SyntaxError):
        return None
    returns = [node for node in ast.walk(tree)
               if isinstance(node, ast.Return) and node.value is not None]
    if not returns:
        return None
    text = ast.unparse(returns[0].value).replace("self.", "o.")
    return text + (" ..." if len(returns) > 1 else "")


def _attnames(model):
    """{relation name: column name} where they differ - author -> author_id."""
    return {f.name: f.attname for f in model._meta.get_fields()
            if f.is_relation and f.concrete and getattr(f, "attname", f.name) != f.name}


def _scalars(model, short=False):
    """[(name, type label, choices or None)] for every non-relation field."""
    out = []
    for f in model._meta.get_fields():
        if f.is_relation:
            continue
        choices = getattr(f, "choices", None)
        values = "|".join(str(v) for v, _label in choices) if choices else None
        out.append((f.name, _type_label(f, short), values))
    return out


def _rel_label(name, attname, rel, tokens, width=None):
    """`author/author_id -> Author? (.books)`.

    The _id column joins in when the exercise filters on it; the trailing
    `(.name)` is what this relation is called from the other side.
    """
    label = f"{name} {rel.arrow}"
    if attname and attname in tokens:
        both = f"{name}/{attname} {rel.arrow}"
        label = both if width is None or len(both) + 2 <= width else f"{attname} {rel.arrow}"
    if rel.reverse:
        label += f" (.{rel.reverse})"
    return label


def describe(model, width=40, keep=None, mark_more=True, tokens=()):
    """['Author', '  firstname lastname ...', '  books <- Book.author', ...].

    `keep` limits which relations are listed (None = all of them).
    """
    fields = _scalars(model)
    lines = [model.__name__]
    longest_type = max((len(t) for _n, t, _c in fields), default=0)
    longest_name = max((len(name) for name, _t, _c in fields), default=0)
    pad = max(0, min(longest_name, width - 3 - longest_type))
    for name, kind, choices in fields:
        lines.append(f"  {name:<{pad}} {kind}".rstrip())
        if choices:
            for line in textwrap.wrap(choices, width - 4, initial_indent="    ",
                                      subsequent_indent="    "):
                lines.append(line)
    rels, attnames, hidden = _relations(model), _attnames(model), 0
    for name, rel in rels.items():
        if keep is None or name in keep:
            label = _rel_label(name, attnames.get(name), rel, tokens, width)
            lines += textwrap.wrap(label, max(16, width - 2), initial_indent="  ",
                                   subsequent_indent="      ") or ["  " + label]
        else:
            hidden += 1
    if hidden and mark_more:
        lines.append(f"  +{hidden} more relation{'s' if hidden > 1 else ''}")
    expression = _str_expr(model)
    if expression:
        lines.append("")
        lines += textwrap.wrap(f"str: {expression}", max(16, width - 2),
                               initial_indent="  ", subsequent_indent="        ")
    return lines


def relevant(exercise, consume_src=None, limit=4):
    """Which models does this exercise involve, and which of their relations?"""
    models = _models()
    models_by_alias = dict(models, Books=models["Book"])
    text = " ".join(filter(None, [exercise.solution, consume_src or "", exercise.prompt]))
    tokens = set(re.split(r"[^A-Za-z_]+", text.replace("__", " ")))

    def mentioned(model, accessor):
        """Either the accessor (author) or its column (author_id) appears."""
        attname = _attnames(model).get(accessor)
        return accessor in tokens or (attname is not None and attname in tokens)

    picked = []
    for name in re.findall(r"\b[A-Z][A-Za-z]*\b", text):   # models named outright
        model = models_by_alias.get(name)
        if model is not None and model not in picked:
            picked.append(model)
    for _ in range(2):                                      # then what they relate to
        for model in list(picked):
            for accessor, rel in _relations(model).items():
                if (mentioned(model, accessor) and rel.target is not None
                        and rel.target not in picked and len(picked) < limit):
                    picked.append(rel.target)
    picked = picked[:limit] or [models["Book"]]
    # a relation is worth showing if the exercise mentions it, or if it links two
    # models that are both on display
    keep = {}
    for model in picked:
        keep[model] = {
            name for name, rel in _relations(model).items()
            if mentioned(model, name) or (rel.target in picked and rel.target is not model)
        }
    return picked, keep, tokens


def panel(exercise, consume_src=None, width=40, limit=4, max_lines=28):
    """The models this exercise involves - everything about them if it fits.

    First try: every field and every relation. If that is taller than the window
    allows, fall back to the relations in play, and only then start dropping models.
    """
    picked, keep, tokens = relevant(exercise, consume_src, limit)
    blocks = None
    for keep_map in (None, keep):
        blocks = [describe(model, width, None if keep_map is None else keep_map[model],
                           tokens=tokens) for model in picked]
        if sum(map(len, blocks)) + len(blocks) - 1 <= max_lines:
            out = []
            for block in blocks:
                if out:
                    out.append("")
                out += block
            return out
    out = []
    for index, block in enumerate(blocks):
        if out and len(out) + len(block) + 1 > max_lines:
            out.append(f"  (+{len(picked) - index} more model(s), :m)")
            break
        if out:
            out.append("")
        out += block
    return out[:max_lines]


def full(width=78):
    lines = []
    for model in _models().values():
        if lines:
            lines.append("")
        lines += describe(model, width, mark_more=False)
    return lines
