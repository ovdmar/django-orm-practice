# django-orm-practice

A Django ORM drill for the terminal. It loads a seeded database into memory, hands you one task at
a time, runs the query you type, and grades it **twice**: did it return the right answer, and how
many SQL queries did it cost compared with the reference solution.

86 exercises, from `filter()` warm-ups to `Prefetch(to_attr=...)`, window functions and the
`Count(distinct=True)` join-multiplication trap.

```
:h help  tab completes fields  :s solution  :hint  :dr result  :sr sql+rows  :n next  :mode easy/medium/hard
──────────────────────────────────────────────────────────────────────────────────────────────────────────
Exercise #54 of 86 · easy
──────────────────────────────────────────────────────────────────────────────────────────────────────────
easy 9/31                          │ Author                       │ >>> Author.objects.filter(pk__lte=20)
++~++~++~@.....................    │   id        AutoField(pk)     │ ~ correct, but 21 queries instead of 2
                                   │   firstname CharField(100)    │ the repeated query below is the N+1
Authors with pk <= 20, each with   │   joindate  DateField         │
their books.                       │   books <- Book.author        │ ["Alvarez", ["Abandoned Compass II", …
                                   │   +7 more relations           │ 20 rows in all - :dr for all of them
budget: 2 queries                  │                               │
                                   │ Book                         │ sql - 21 queries, 2 distinct:
                                   │   id    AutoField(pk)         │ 1. SELECT author.id, +8 cols
                                   │   title CharField(100)        │    WHERE author.id <= 20
                                   │   author -> Author?           │ 2. x20 SELECT book.id, +8 cols
                                   │   +8 more relations           │    WHERE book.author_id = 1

  the grader consumes your result like this:
    lambda qs: [(a.lastname, sorted(b.title for b in a.books.all())) for a in qs]
  try again, :hint, or :s for the solution
```

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ovdmar/django-orm-practice/main/install.sh | sh
```

Needs `curl`, `tar` and `python3` — no git, no sudo. It unpacks the latest
[release](https://github.com/ovdmar/django-orm-practice/releases) into
`~/.local/share/django-orm-practice`, installs Django into a virtualenv of its own (nothing outside
that directory is touched) and links an `orm` command into `~/.local/bin`. Re-run it to update;
your progress lives elsewhere and is left alone.

Or download it yourself:

```bash
curl -fsSL https://github.com/ovdmar/django-orm-practice/releases/latest/download/django-orm-practice.tar.gz | tar -xz
cd django-orm-practice && ./setup.sh && ./orm
```

## Run

```bash
orm                        # asks which difficulty, then picks up where you left off
orm --level hard           # practise the hard ones
orm --from 41              # start at exercise 41
orm --list                 # what is in it, and what you have solved
orm --verify               # run all 86 reference solutions (the test suite)
```

It asks which difficulty to practise, defaults to the first one with anything left, and moves on to
the next difficulty when you finish one. Within a difficulty you get the exercises you have not
solved first. Progress is kept in `~/.config/django-orm-practice/progress.json`.

Type a query at `>>>` — every model and `Q`, `F`, `Count`, `Prefetch`, `OuterRef` … are already
imported, and **tab completes** model names, attributes and `__` field paths. An expression runs on
enter; for several statements keep typing and send a blank line.

| | |
|---|---|
| `:s` / `:hint` | the reference solution and its explanation / a nudge |
| `:dr` / `:sr` | your result in full / every query with the rows it returned |
| `:diff` / `:err` | your answer against the reference / the traceback |
| `:n` `:p` `:g N` | next, previous, jump — `alt+↑/↓` revisits earlier screens |
| `:mode` `:l` `:m` | switch difficulty / list exercises / the whole schema |
| `:h` | all of them |

## Credit

The models and the first 40 exercises come from
[Django ORM — Examples and Practice Problems](https://plainenglish.io/python/django-orm-examples-and-practice-problems),
which is where this started. The other 46 exist because that article is light on query counts:
everything from exercise 41 on is about `select_related`, `prefetch_related` and the cost of
getting the right answer the wrong way.

[docs/DESIGN.md](docs/DESIGN.md) covers how the grading, the schema panel and the checks work, and
how to add exercises.

MIT licensed.
