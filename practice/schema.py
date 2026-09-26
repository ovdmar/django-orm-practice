"""A compact schema reminder, narrowed down to the models an exercise touches."""

import re
import textwrap

FORWARD = {"ForeignKey": "->", "OneToOneField": "->1", "ManyToManyField": "<->"}


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
            out[f.name] = (None, "-> any model (content_type + object_id)")
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


def describe(model, width=40, keep=None, mark_more=True):
    """['Author', '  firstname lastname ...', '  books <- Book.author', ...].

    `keep` limits which relations are listed (None = all of them).
    """
    plain = [f.name for f in model._meta.get_fields()
             if not f.is_relation and f.name != "id"]
    lines = [model.__name__]
    if plain:
        lines += textwrap.wrap(" ".join(plain), width - 2,
                               initial_indent="  ", subsequent_indent="  ")
    rels = _relations(model)
    hidden = 0
    for name, (_, arrow) in rels.items():
        if keep is None or name in keep:
            lines.append(f"  {name} {arrow}")
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

    picked = []
    for name in re.findall(r"\b[A-Z][A-Za-z]*\b", text):   # models named outright
        model = models_by_alias.get(name)
        if model is not None and model not in picked:
            picked.append(model)
    for _ in range(2):                                      # then what they relate to
        for model in list(picked):
            for accessor, (target, _arrow) in _relations(model).items():
                if (accessor in tokens and target is not None
                        and target not in picked and len(picked) < limit):
                    picked.append(target)
    picked = picked[:limit] or [models["Book"]]
    # a relation is worth showing if the exercise mentions it, or if it links two
    # models that are both on display
    keep = {}
    for model in picked:
        keep[model] = {
            name for name, (target, _a) in _relations(model).items()
            if name in tokens or (target in picked and target is not model)
        }
    return picked, keep


def panel(exercise, consume_src=None, width=40, limit=4, max_lines=28):
    picked, keep = relevant(exercise, consume_src, limit)
    out = []
    for model in picked:
        block = describe(model, width, keep[model])
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
    picked, keep = relevant(exercise, consume_src, limit)
    out = []
    for model in picked:
        fields = [f.name for f in model._meta.get_fields()
                  if not f.is_relation and f.name != "id"]
        all_rels = _relations(model)
        rels = [f"{n} {a}" for n, (_t, a) in all_rels.items() if n in keep[model]]
        hidden = len(all_rels) - len(rels)
        if hidden:
            rels.append(f"+{hidden} more")
        body = " ".join(fields)
        if rels:
            body += "  ·  " + ", ".join(rels)
        out += textwrap.wrap(f"{model.__name__}: {body}", width,
                             subsequent_indent="    ") or [model.__name__]
    return out
