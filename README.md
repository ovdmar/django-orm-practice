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

Every screen has the same three columns — the task, your attempt, the schema — with one line of
shortcuts above it, so nothing has to be memorised and nothing moves when an attempt lands:

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

Rows are clipped to the column; `:v` opens the whole answer in a full-screen pager (`q`
leaves it), `:v ref` does the same for the reference answer and `:v sql` for every query the
attempt ran.

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

**Enter adds a line; shift+enter runs it.** So a two-statement answer is typed as two lines and
graded as one measured unit — each submission gets a fresh namespace and is rolled back, so it
has to arrive together. A reminder sits above the prompt:

```
  enter = new line   shift+enter = run   (alt+enter and ctrl+j run it too)
```

Those alternatives are not decoration. **Shift+Enter is indistinguishable from Enter in most
terminals** — only those implementing the kitty keyboard protocol (`\e[13;2u`: kitty, WezTerm,
Ghostty, foot) or xterm's `modifyOtherKeys` (`\e[27;2;13~`) send something different. All four
sequences are bound, and **alt+enter** and **ctrl+j** work everywhere, so you always have a way
to submit. `:key` reports what your terminal sends for any combination.

**ctrl+c** clears whatever you are typing and gives you a fresh prompt — and aborts a query of
your own that is still running, without ending the session. To leave, use **ctrl+d**, `exit()`
or `:q`.

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
