"""Progress lives in a JSON file next to the code, so a session can be resumed."""

import json
import os
from datetime import datetime

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".progress.json")
VERSION = 1


def load():
    try:
        with open(PATH) as fh:
            data = json.load(fh)
        if data.get("version") == VERSION:
            data.setdefault("exercises", {})
            return data
    except (OSError, ValueError):
        pass
    return {"version": VERSION, "current": 1, "exercises": {}}


def save(data):
    tmp = PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    os.replace(tmp, PATH)


def entry(data, slug):
    return data["exercises"].setdefault(
        slug, {"attempts": 0, "solved": False, "best_queries": None, "target": None,
               "solution_shown": False, "solved_at": None}
    )


def record_attempt(data, exercise, grade):
    e = entry(data, exercise.slug)
    e["attempts"] += 1
    e["target"] = grade.target
    if grade.ok:
        if e["best_queries"] is None or grade.nqueries < e["best_queries"]:
            e["best_queries"] = grade.nqueries
        if not e["solved"]:
            e["solved"] = True
            e["solved_at"] = datetime.now().isoformat(timespec="seconds")
    save(data)
    return e


def mark_shown(data, exercise):
    entry(data, exercise.slug)["solution_shown"] = True
    save(data)


def set_current(data, number):
    data["current"] = number
    save(data)


def first_unsolved(data, exercises):
    for ex in exercises:
        if not data["exercises"].get(ex.slug, {}).get("solved"):
            return ex.number
    return exercises[-1].number


def summary(data, exercises):
    solved = sum(1 for e in exercises if data["exercises"].get(e.slug, {}).get("solved"))
    clean = sum(
        1 for e in exercises
        if (d := data["exercises"].get(e.slug, {})).get("solved")
        and not d.get("solution_shown")
        and d.get("best_queries") is not None
        and d.get("target") is not None
        and d["best_queries"] <= d["target"]
    )
    return solved, clean, len(exercises)


def reset():
    try:
        os.remove(PATH)
    except OSError:
        pass
