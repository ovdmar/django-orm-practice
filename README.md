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

The shortcut bar sits above every screen, so nothing has to be memorised. A task is posed
with the schema beside it:

```
:h help   :s solution   :hint   :v view all (q exits)   :diff   :sql   :n next   :p prev   :g N goto
:l list   :m models   :sc schema   :lay layout   :ml multi-line (blank line runs)   :stats   :q quit
────────────────────────────────────────────────────────────────────────────────────
54/86  Reverse FK   [prefetch_related]
────────────────────────────────────────────────────────────────────────────────────
  Authors with pk <= 20, each with their books.   │ Author
                                                  │   firstname lastname address zipcode
  budget: 2 queries                               │   telephone joindate popularity_score
                                                  │   books <- Book.author
                                                  │   +7 more relations
                                                  │
                                                  │ Book
                                                  │   title genre price published_date
                                                  │   author -> Author?
                                                  │   +8 more relations

  the grader consumes your result like this:
    lambda qs: [(a.lastname, sorted(b.title for b in a.books.all())) for a in qs]
>>>
```

Every attempt then repaints as three columns — task, what you ran and what came back,
schema:

```
─────────────────────────────────────────────────────────────────────────────────────────────────────
Authors with pk <= 20, each  │ >>> Author.objects.filter(pk__lte=20)              │ Author
with their books.            │ ~ correct, but 21 queries instead of 2             │   firstname lastname
                             │ 20x SELECT "bookstore_book"."id", "bookstore_boo…  │   telephone joindate
budget: 2 queries            │ that repeated shape is the N+1                     │   popularity_score
                             │                                                    │   books <- Book.author
                             │ ["Alvarez", ["Abandoned Compass II", "Bitter Har…  │   +7 more relations
                             │ ["Bianchi", ["Abandoned Harvest", "Bitter Cabin …  │
                             │ 20 rows in all - :v to view it all                 │ Book
  try again, :hint, or :s for the solution                                        │   title genre price
```

Rows are clipped to the column; `:v` opens the whole answer in a full-screen pager (`q`
leaves it), `:v ref` does the same for the reference answer and `:v sql` for every query the
attempt ran.

### Layout

`auto` picks by terminal width: three columns from 130 columns, two (result + schema) from 96,
and below that everything stacks with the schema as one line per model. `:lay` cycles
`auto / 3 / 2 / stack` and remembers the choice; `./orm --layout 3` forces one from the start.
The schema column lists only the models that exercise involves and only the relations in play
(`+N more relations` for the rest, `:m` for the whole schema); `:sc` hides it, `--no-schema`
starts without it.

### Typing answers

Type a query at `>>>`. The value of the last expression in your snippet is what gets graded
(or a variable named `answer`).

* A **complete expression** runs the moment you hit enter — that covers most exercises.
* For **several statements**, type it like a file: an assignment or an open block keeps the
  reader collecting (dedent to close a block), and a **blank line runs the whole snippet** as
  one measured unit. If the first line is already a complete expression, end it with a `\` or
  open the snippet with `:ml` so it does not run early.

Each submission gets a fresh namespace and is rolled back, so an answer that needs two
statements has to arrive as one snippet.

### Commands

The bar above each exercise lists these; `:h` prints them with descriptions and `:k` hides the
bar (`--no-keys` starts without it).

```
:ml :multi     start a multi-statement snippet (blank line runs it)
:s :solution   reference solution + the lesson behind it
:hint          one hint at a time
:v :view       full-screen preview of your answer, q to leave
               :v ref  the reference answer    :v sql  every query it ran
:sql           the SQL your last attempt ran, inline (repeats collapsed)
:diff          reference answer vs yours
:n :p :g N     next / previous / jump to N
:l :list       all exercises and your progress     :stats   progress summary
:m :models     the whole schema                    :d :data row counts
:sc :schema    toggle the per-exercise schema reminder
:lay :layout   cycle the column layout (auto / 3 / 2 / stack)
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
