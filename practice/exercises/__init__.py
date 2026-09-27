from . import a_basics, b_select_related, c_prefetch, d_advanced
from ._base import LEVELS, SECTIONS, Exercise, collect

EXERCISES = collect(a_basics, b_select_related, c_prefetch, d_advanced)
BY_SLUG = {e.slug: e for e in EXERCISES}


def get(number):
    """The exercise with that number, or None - including for a number of None."""
    if isinstance(number, int) and 1 <= number <= len(EXERCISES):
        return EXERCISES[number - 1]
    return None
