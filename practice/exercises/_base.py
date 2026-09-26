from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

LEVELS = ("easy", "medium", "hard")

SECTIONS = {
    "basics": "Warm-up: filtering, ordering, aggregation (the article's 40)",
    "select_related": "select_related: killing N+1 across forward FK / O2O",
    "prefetch_related": "prefetch_related: M2M, reverse FK, Prefetch(), nesting",
    "advanced": "annotate / Subquery / window functions / conditional aggregation",
}


@dataclass
class Exercise:
    slug: str
    section: str
    title: str
    prompt: str
    solution: str
    consume: Optional[Callable] = None
    hints: Sequence[str] = ()
    order_matters: bool = False
    naive: Optional[str] = None   # correct but query-hungry; --verify proves it costs more
    notes: str = ""               # the lesson, shown together with the solution
    level: str = "medium"         # easy / medium / hard
    mutates: bool = False
    number: int = 0

    @property
    def label(self):
        return f"{self.number:>2}. {self.title}"


def collect(*modules):
    out = []
    for mod in modules:
        for ex in mod.EXERCISES:
            ex.number = len(out) + 1
            out.append(ex)
    return out
