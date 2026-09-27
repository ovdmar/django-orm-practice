import inspect
import re
import textwrap
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

LEVELS = ("easy", "medium", "hard")

SECTIONS = {
    "basics": "Warm-up: filtering, ordering, aggregation (the article's 40)",
    "select_related": "select_related: killing N+1 across forward FK / O2O",
    "prefetch_related": "prefetch_related: M2M, reverse FK, Prefetch(), nesting",
    "advanced": "annotate / Subquery / window functions / conditional aggregation",
}


def consume_source(fn):
    """The consume lambda's source, read once at import.

    inspect.getsource() locates a lambda by line number and reads the file live, so
    resolving this lazily would show a neighbouring exercise's lambda after the file
    is edited under a running session. Captured here, it cannot drift.
    """
    if fn is None:
        return ""
    try:
        source = textwrap.dedent(inspect.getsource(fn)).strip()
    except (OSError, TypeError):
        return ""
    return re.sub(r"^consume\s*=\s*", "", source).rstrip(",")


@dataclass
class Exercise:
    slug: str                     # the stable id: progress is keyed by it, so exercises
                                  # can be renumbered or reordered without losing anything
    section: str
    title: str
    prompt: str
    solution: str
    consume: Optional[Callable] = None
    hints: Sequence[str] = ()
    order_matters: bool = False
    naive: Optional[str] = None   # correct but query-hungry; --verify proves it costs more
    setup: Optional[Callable] = None   # returns names to hand the snippet, unmeasured
    notes: str = ""               # the lesson, shown together with the solution
    contract: str = ""            # consume's source, filled in at import
    # (kind, code, why) where kind is "good" (right and idiomatic), "careful" (right
    # here, but fragile - portability, memory, a latent bug) or "bad" (wrong or slower)
    alternatives: Sequence[tuple] = ()
    level: str = "medium"         # easy / medium / hard
    added: str = "2026-09-26"     # when it joined the set - new ones sort last
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
            ex.contract = consume_source(ex.consume)
            out.append(ex)
    return out
