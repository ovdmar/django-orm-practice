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

Every screen has the same three columns — the task, the schema, your attempt (the widest, on the
right) — with one line of shortcuts above it, so nothing has to be memorised and nothing moves when an attempt lands:

```
:h help   :s solution   :hint   :v view   :diff   :sql   :n next   :p prev   :g N goto   :l list   :m models   alt+up/dn screens   ^c clear   ^d quit
────────────────────────────────────────────────────────────────────────────────────
Exercise #54 of 86   [prefetch_related]
────────────────────────────────────────────────────────────────────────────────────
  Authors with pk <= 20,   │ >>> ...                        │ Author
  each with their books.   │                                │   id               AutoField(pk)
                           │ your rows and the SQL they     │   firstname        CharField(100)
  budget: 2 queries        │ cost appear here               │   lastname         CharField(100)
                           │                                │   joindate         DateField
                           │                                │   popularity_score IntegerField
                           │                                │   books <- Book.author
                           │                                │   +7 more relations

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

Once an answer is correct **and** within budget, the reference solution is printed next to
yours so you can compare wording:

```
  ✓ correct, 2 queries - optimal

  reference solution, 2 queries:
    Author.objects.filter(pk__lte=20).prefetch_related('books')
  yours, 2 queries:
    Author.objects.filter(pk__lte=20).prefetch_related(Prefetch("books", queryset=Book.objects.all()))

  select_related cannot do this: a reverse FK is multi-valued, so it needs its own query.
```

(If the two match bar quoting and whitespace it just says so. This does not count as revealing
the solution — you had already solved it. A *correct but over budget* answer deliberately does
not print it, since the query count is still the open question; `:s` if you want it anyway.)

When the answer is **wrong**, the column shows the difference instead of your rows — which rows
are missing, which ones the reference does not have, or, when the rows match, that only the order
is off:

```
✗ wrong answer (1 query)

you returned 15 row(s), the reference has 20
5 row(s) missing from yours:
  ["Broken Compass", "Fischer"]
  ["Alvarez", "Bitter Meridian"]
  ... 2 more
:v for your rows, :v ref for the reference, :diff for both
```

Dict answers are compared key by key (`missing key(s): total_price`), scalars head to head
(`expected: 8096 / you have: 6364`), and a wrong shape is named as such (`expected a list of 700
row(s), you returned a number`).

Everything in that column wraps rather than being cut off — rows, error messages, the SQL. A row
that would take more than three lines is the exception: it is trimmed with `...`. `:v` opens the
whole answer in a full-screen pager (`q` leaves it), `:v ref` does the same for the reference
answer, `:v sql` for every query the attempt ran, and `:v err` for the full traceback.

When your snippet raises, the snippet itself is printed with the offending line marked, so you
can see where it broke rather than reading engine frames:

```
✗ your code raised
TypeError: ...remove() argument after * must be an iterable, not int

  1 a = Author.objects.get(pk=1)
  2 f = a.followers.order_by("id").values_list("id",
     flat=True).first()
> 3 a.followers.remove(*f)
:v err for the traceback
```

### Screens

Each exercise takes the whole window: the screen is redrawn from the top and every screen is
sized to fit your terminal, so nothing scrolls away mid-exercise. Because that costs you the
scrollback, the session keeps its screens and you can step back through them:

```
alt+↑ / alt+↓      the previous / next screen of this session  (ctrl+↑ / ctrl+↓ also work)
:b :back  :f :fwd  the same thing, typed
```

Stepping onto an older screen also makes that exercise current, so you can pick up where that
screen left off — the footer says which exercise the prompt belongs to.

**Cmd+arrows cannot be used.** macOS terminals keep Cmd for themselves and Linux window
managers grab Super, so nothing reaches the program. Alt/Option and Ctrl do arrive. If your
terminal sends something else, `:key` prints the escape sequence it produced and the `~/.inputrc`
line that binds it.

`:fs` turns fullscreen off if you would rather screens scrolled past each other
(`--no-fullscreen` to start that way).

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

**ctrl+c** clears whatever you are typing and gives you a fresh prompt — and aborts a query of
your own that is still running, without ending the session. To leave, use **ctrl+d**, `exit()`
or `:q`.

### Tab completion

`tab` completes three things, working out which from the line you are typing:

```
Auth<TAB>                            Author, AuthorProfile
Book.pub<TAB>                        Book.published_date, Book.publisher, Book.publisher_id
Book.objects.values_list('pub<TAB>   published_date, publisher, publisher_id
Book.objects.select_related('pub<TAB>  publisher          - only what it can join
Author.objects.filter(books__reviews__rat<TAB>   books__reviews__rating
Book.objects.filter(price__<TAB>     price__gte, price__icontains, price__isnull, ...
```

Field paths walk `__` hops through the relations, offer lookups once the path reaches a plain
field, and are completed against the model named last in the line — so a nested
`Prefetch('books', queryset=Book.objects.filter(...))` completes against `Book`, not the outer
model. `select_related()` is offered only relations it can actually join, `prefetch_related()`
any relation.

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
* `tests/test_screen_history.py` drives the CLI through a pty and checks alt/ctrl+arrows really
  move between screens while plain arrows stay with readline history;
  `tests/test_frames_fit.py` builds both screens of all 86 exercises at four terminal heights
  and three widths and asserts none of them overflows the window.
* `.venv/bin/python tests/test_prompt_width.py` drives the CLI through a pty and checks that
  readline knows the true width of the coloured prompt — get that wrong and the visible cursor
  refuses to walk back over the first few characters of your query.
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
