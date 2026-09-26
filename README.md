# django-orm-practice

An ORM drill you run in a terminal. It loads a seeded database into memory, hands you one
task at a time, runs whatever query you type, and grades it twice: **did it return the right
answer**, and **how many SQL queries did it take** compared with the reference solution.

86 exercises, in four sections:

| section | n | what it drills |
|---|---|---|
| `basics` | 40 | the 40 problems from the [plainenglish.io article](https://plainenglish.io/python/django-orm-examples-and-practice-problems) — filtering, ordering, aggregation, M2M writes |
| `select_related` | 13 | forward FK, one-to-one in both directions, chains through nullable FKs, `only()` traps |
| `prefetch_related` | 15 | reverse FK, M2M, `Prefetch(queryset=…, to_attr=…)`, nesting, through models, generic FK |
| `advanced` | 18 | `annotate` join multiplication, `Subquery`/`OuterRef`, window functions, conditional aggregates, `update(F(...))` |

## Setup

```bash
./setup.sh
```

Creates `.venv` and installs Django. (It bootstraps pip from `pip.pyz` if your system has
no pip — no sudo needed.)

## Run

```bash
./orm
```

With no arguments it resumes where you left off. Progress lives in `.progress.json`.

```bash
./orm --from 41            # start at exercise 41
./orm --only 54            # drill exercise 54 alone, do not advance
./orm --section prefetch_related
./orm --list               # all exercises, with what you have solved
./orm --restart            # wipe progress
./orm --verify             # run all 86 reference solutions, print their query budgets
```

## What a turn looks like

```
──────────────────────────────────────────────────────────────────────────────
54/86  Reverse FK   [prefetch_related]
──────────────────────────────────────────────────────────────────────────────
  Authors with pk <= 20, each with their books.

  the grader consumes your result like this:
    lambda qs: [(a.lastname, sorted(b.title for b in a.books.all())) for a in qs]

  budget: 2 queries
>>> Author.objects.filter(pk__lte=20)
  ~ correct, but 21 queries instead of 2
    20x  SELECT "bookstore_book"."id", "bookstore_book"."title", ...
    that repeated shape is the N+1 - fetch it up front instead
>>> Author.objects.filter(pk__lte=20).prefetch_related("books")
  ✓ correct, 2 queries - optimal
```

The **"the grader consumes your result like this"** block is the contract: it is the actual
code that will touch your result, so it tells you which related objects get walked — which is
exactly what decides your query count. Return the queryset (or list of objects); don't do the
walking yourself.

Type a query at `>>>`. Multi-line input continues until the statement is complete, so
assignments, loops and a final expression all work — the value of the last expression is
graded (or a variable named `answer`).

### Commands

```
:s :solution   reference solution + the lesson behind it
:hint          one hint at a time
:sql           the SQL your last attempt actually ran (repeats collapsed)
:diff          reference answer vs yours
:n :p :g N     next / previous / jump to N
:l :list       all exercises and your progress     :stats   progress summary
:m :models     the schema                          :d :data row counts
:reset         wipe progress                       :q       quit
```

## How the grading works

* Every attempt runs inside a `transaction.atomic()` block that is **always rolled back**, so
  exercises may create/update/delete freely and the next exercise still sees pristine data.
* Queries are counted with `CaptureQueriesContext`; `SAVEPOINT`/`RELEASE`/`COMMIT` noise is
  filtered out, so the count is only the SQL your query actually caused.
* The budget is not hardcoded: the reference solution is executed against the same data and
  *its* query count is the target. Beat it and the drill says so.
* Answers are compared after deep normalisation (models → `Model#pk`, dates → ISO, decimals
  rounded, lists sorted unless the task says the order matters), so `values_list` order or a
  set vs a list will not fail you — but returning dicts where tuples were asked for will.
* `./orm --verify` is the test suite: every reference solution must run, return a non-empty
  answer, and — where the exercise ships a deliberately naive variant — that variant must
  return the *same* answer in *more* queries. That is what keeps the budgets honest.

## The schema

`bookstore/models.py`. `User`, `Author`, `Publisher` and `Book` are the article's models, field
names included (`firstname`, `joindate`, `popularity_score`, `recommendedby`, `published_date`),
so the article's problems can be solved verbatim. `Book` is the article's `Books` — both names
work in the REPL.

The rest exists to make the later sections interesting:

```
Author ──1:1── AuthorProfile          Author ──self FK── recommendedby
Author ──M2M── User (followers)       Book ──M2M── Author (contributors)
Publisher ──1:N── Series ──1:N── Book
Book ──1:N── Review ──N:1── User
Order ──1:N── OrderItem ──N:1── Book
Store ──M2M(through StoreStock)── Book
Tag ──1:N── TaggedItem ──GenericFK── Book | Author
```

Row counts: 700 books, 150 authors, 1200 reviews, 6217 follower links, ~12.4k rows overall.
The data is generated from a fixed RNG seed, so the answers — and the query budgets — are the
same on every run.

## Adding exercises

One entry in `practice/exercises/{a_basics,b_select_related,c_prefetch,d_advanced}.py`:

```python
E(slug="pf-author-books", section=S, title="Reverse FK",
  prompt="Authors with pk <= 20, each with their books.",
  consume=lambda qs: [(a.lastname, sorted(b.title for b in a.books.all())) for a in qs],
  solution="Author.objects.filter(pk__lte=20).prefetch_related('books')",
  naive="Author.objects.filter(pk__lte=20)",
  hints=["..."], notes="the lesson, shown with the solution")
```

`consume` is the grader's contract and is shown to you verbatim — keep it to one line.
`order_matters=True` if the task specifies an ordering; `mutates=True` for writes. Then run
`./orm --verify` to confirm the new exercise answers something and that `naive` really is
slower.
