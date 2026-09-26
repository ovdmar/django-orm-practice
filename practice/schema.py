"""A compact schema reminder, narrowed down to the models an exercise touches."""

import re
import textwrap

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
    """{accessor name: (target model, rendered arrow)} for every relation on `model`."""
    out = {}
    for f in model._meta.get_fields():
        if not f.is_relation:
            continue
        if type(f).__name__ == "GenericForeignKey":
            out[f.name] = (None, "-> any model")
            continue
        if f.related_model is None:
            continue
        target = f.related_model.__name__
        if f.concrete:
            arrow = FORWARD.get(type(f).__name__, "->")
            null = "?" if getattr(f, "null", False) else ""
            out[f.name] = (f.related_model, f"{arrow} {target}{null}")
        elif type(f).__name__ == "GenericRelation":
            out[f.name] = (f.related_model, f"<-> {target} (generic)")
        else:
            name = f.get_accessor_name()
            if name is None:
                continue
            kind = {"OneToOneRel": "<-1", "ManyToManyRel": "<->"}.get(type(f).__name__, "<-")
            via = f"{target}.{f.remote_field.name}" if kind == "<-" else target
            out[name] = (f.related_model, f"{kind} {via}")
    return out


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


def _rel_label(name, attname, arrow, tokens, width=None):
    """Show the _id column alongside the accessor when the exercise uses it.

    If both names will not fit the panel, keep the one the exercise used.
    """
    if not (attname and attname in tokens):
        return f"{name} {arrow}"
    both = f"{name}/{attname} {arrow}"
    if width is None or len(both) + 2 <= width:
        return both
    return f"{attname} {arrow}"


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
    for name, (_, arrow) in rels.items():
        if keep is None or name in keep:
            lines.append("  " + _rel_label(name, attnames.get(name), arrow, tokens, width))
        else:
            hidden += 1
    if hidden and mark_more:
        lines.append(f"  +{hidden} more relation{'s' if hidden > 1 else ''}")
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
            for accessor, (target, _arrow) in _relations(model).items():
                if (mentioned(model, accessor) and target is not None
                        and target not in picked and len(picked) < limit):
                    picked.append(target)
    picked = picked[:limit] or [models["Book"]]
    # a relation is worth showing if the exercise mentions it, or if it links two
    # models that are both on display
    keep = {}
    for model in picked:
        keep[model] = {
            name for name, (target, _a) in _relations(model).items()
            if mentioned(model, name) or (target in picked and target is not model)
        }
    return picked, keep, tokens


def panel(exercise, consume_src=None, width=40, limit=4, max_lines=28):
    picked, keep, tokens = relevant(exercise, consume_src, limit)
    out = []
    for model in picked:
        block = describe(model, width, keep[model], tokens=tokens)
        if out and len(out) + len(block) + 1 > max_lines:
            out.append(f"  (+{len(picked) - picked.index(model)} more model(s), :m)")
            break
        if out:
            out.append("")
        out += block
    return out


def full(width=78):
    lines = []
    for model in _models().values():
        if lines:
            lines.append("")
        lines += describe(model, width, mark_more=False)
    return lines


def compact(exercise, consume_src=None, width=76, limit=4):
    """One wrapped line per model - for terminals too narrow for a sidebar."""
    picked, keep, tokens = relevant(exercise, consume_src, limit)
    out = []
    for model in picked:
        fields = [f"{n}:{t}" + (f"[{c}]" if c else "")
                  for n, t, c in _scalars(model, short=True)]
        all_rels, attnames = _relations(model), _attnames(model)
        rels = [_rel_label(n, attnames.get(n), a, tokens)
                for n, (_t, a) in all_rels.items() if n in keep[model]]  # compact mode wraps
        hidden = len(all_rels) - len(rels)
        if hidden:
            rels.append(f"+{hidden} more")
        body = " ".join(fields)
        if rels:
            body += "  ·  " + ", ".join(rels)
        out += textwrap.wrap(f"{model.__name__}: {body}", width,
                             subsequent_indent="    ") or [model.__name__]
    return out
