"""prefetch_related(): a second query instead of N, for the multi-valued side."""

from ._base import Exercise as E

S = "prefetch_related"


def _books_in_memory():
    """Hand the snippet a plain list of Book objects, fetched off the clock."""
    from bookstore.models import Book

    return {"books": list(Book.objects.order_by("pk")[:30])}

EXERCISES = [
    E(slug="pf-author-books", level="easy", section=S, title="Reverse FK",
      prompt="Authors with pk <= 20, each with their books.",
      consume=lambda qs: [(a.lastname, sorted(b.title for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=20).prefetch_related('books')",
      naive="Author.objects.filter(pk__lte=20)",
      notes="select_related cannot do this: a reverse FK is multi-valued, so it needs its own query "
            "(one, not one per author).",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk__lte=20).select_related('books')",
           "select_related cannot follow a reverse FK - it raises rather than guessing"),
          ("bad",
           "Author.objects.filter(pk__lte=20)",
           "1 query, then one per author for their books"),
      )),

    E(slug="pf-m2m", level="easy", section=S, title="Forward M2M",
      prompt="The first 25 books by pk, with their contributors.",
      consume=lambda qs: [(b.title, sorted(a.lastname for a in b.contributors.all())) for b in qs],
      solution="Book.objects.prefetch_related('contributors').order_by('pk')[:25]",
      naive="Book.objects.order_by('pk')[:25]",
      order_matters=True,
      notes="An M2M prefetch queries the through table joined to the target once, then hands "
             "each object its share in Python. The number of objects does not change the number "
             "of queries.",
      alternatives=(
          ("bad",
           "Book.objects.order_by('pk')[:25]",
           "one query per book for its contributors"),
          ("bad",
           "Book.objects.prefetch_related('contributors__books').order_by('pk')[:25]",
           "right, but it prefetches a level nobody reads - a third query for nothing"),
      )),

    E(slug="pf-reverse-m2m", level="easy", section=S, title="Reverse M2M",
      prompt="The first 15 users by pk, with the authors they follow.",
      consume=lambda qs: [(u.username, sorted(a.lastname for a in u.following.all())) for u in qs],
      solution="User.objects.prefetch_related('following').order_by('pk')[:15]",
      naive="User.objects.order_by('pk')[:15]",
      order_matters=True,
      notes="The reverse side of an M2M costs exactly the same two queries as the forward side. "
             "related_name is the only difference between them.",
      alternatives=(
          ("bad",
           "User.objects.order_by('pk')[:15]",
           "15 more queries, one per user"),
          ("bad",
           "User.objects.prefetch_related('following__books').order_by('pk')[:15]",
           "an extra query for books the contract never touches"),
      )),

    E(slug="pf-to-attr", level="medium", section=S, title="Prefetch(to_attr=…)",
      prompt="Authors with pk <= 25. The grader reads a.expensive_books, which must hold only that "
      "author's books priced >= 50.",
      consume=lambda qs: [(a.lastname, sorted(b.title for b in a.expensive_books)) for a in qs],
      solution="Author.objects.filter(pk__lte=25).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.filter(price__gte=50), to_attr='expensive_books'))",
      hints=["Prefetch(lookup, queryset=…, to_attr=…) - with to_attr the result is a plain list, "
             "not a manager."],
      notes="to_attr keeps the filtered set separate from a.books.all(), which would otherwise be "
            "cached with a *filtered* meaning and surprise the next reader.",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk__lte=25).prefetch_related(\n"
           "    Prefetch('books', queryset=Book.objects.filter(price__gte=50)))",
           "without to_attr the filtered set lands in a.books.all(), and the grader reads a.expensive_books - which then does not exist"),
          ("bad",
           "Author.objects.filter(pk__lte=25).prefetch_related(\n"
           "    Prefetch('books', to_attr='expensive_books'))",
           "the attribute is there but unfiltered: every book, not only those at 50 or more"),
      )),

    E(slug="pf-nested", level="medium", section=S, title="Nested prefetch",
      prompt="Authors with pk <= 15, their books, and each book's reviews.",
      consume=lambda qs: [(a.lastname, sorted((b.title, sorted(r.rating for r in b.reviews.all())) for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=15).prefetch_related('books__reviews')",
      naive="Author.objects.filter(pk__lte=15)",
      notes="One query per level, regardless of how many rows each level has.",
      alternatives=(
          ("good",
           "Author.objects.filter(pk__lte=15).prefetch_related('books', 'books__reviews')",
           "naming the middle level as well changes nothing - 'books__reviews' already fetches books"),
          ("bad",
           "Author.objects.filter(pk__lte=15).prefetch_related('books')",
           "books come in one query, then every book fetches its own reviews"),
      )),

    E(slug="pf-with-select-related", level="medium", section=S, title="select_related inside a prefetch",
      prompt="Authors with pk <= 20 and their books, where the grader also reads each book's publisher.",
      consume=lambda qs: [(a.lastname, sorted((b.title, b.publisher.lastname) for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=20).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.select_related('publisher')))",
      naive="Author.objects.filter(pk__lte=20).prefetch_related('books')",
      notes="The prefetch queryset is a normal queryset - give it its own select_related and the second "
            "level comes back joined.",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk__lte=20).prefetch_related('books')",
           "two queries for the books, then one per book for its publisher"),
          ("bad",
           "Author.objects.filter(pk__lte=20).prefetch_related('books__publisher')",
           "correct, but it pays a third query for publishers a JOIN inside the prefetch would have carried"),
      )),

    E(slug="pf-mixed", level="medium", section=S, title="select_related and prefetch_related together",
      prompt="The first 30 books by pk, with their publisher and their tags (a generic relation).",
      consume=lambda qs: [(b.title, b.publisher.lastname, sorted(t.tag.name for t in b.tags.all())) for b in qs],
      solution="Book.objects.select_related('publisher').prefetch_related('tags__tag').order_by('pk')[:30]",
      naive="Book.objects.select_related('publisher').order_by('pk')[:30]",
      order_matters=True,
      notes="select_related and prefetch_related compose: single-valued relations join into the "
             "first query, multi-valued ones get one of their own. Counting queries is counting "
             "the multi-valued levels.",
      alternatives=(
          ("good",
           "Book.objects.select_related('publisher').prefetch_related(\n"
           "    Prefetch('tags', queryset=TaggedItem.objects.select_related('tag'))).order_by('pk')[:30]",
           "joining tag inside the prefetch instead of prefetching it: 2 queries rather than 3"),
          ("bad",
           "Book.objects.prefetch_related('publisher', 'tags__tag').order_by('pk')[:30]",
           "prefetching a forward FK costs a query a JOIN would have given away"),
      )),

    E(slug="pf-through", level="hard", section=S, title="Prefetch the through model",
      prompt="Stores with pk <= 3, and their stock rows - the grader reads each row's book and quantity.",
      consume=lambda qs: [(s.name, sorted((x.book.title, x.quantity) for x in s.stock.all())) for s in qs],
      solution="Store.objects.filter(pk__lte=3).prefetch_related(\n"
               "    Prefetch('stock', queryset=StoreStock.objects.select_related('book')))",
      naive="Store.objects.filter(pk__lte=3).prefetch_related('stock')",
      notes="store.books.all() hides the through row. When you need quantity/shelf you must go through "
            "StoreStock yourself.",
      alternatives=(
          ("bad",
           "Store.objects.filter(pk__lte=3).prefetch_related('stock')",
           "the stock rows arrive, then each one fetches its own book"),
          ("bad",
           "Store.objects.filter(pk__lte=3).prefetch_related('books')",
           "books skips the through row, so quantity is nowhere to be read"),
      )),

    E(slug="pf-filtered-m2m", level="medium", section=S, title="Filtered M2M prefetch",
      prompt="All stores. The grader reads s.premium: the books that store stocks priced > 55.",
      consume=lambda qs: [(s.name, sorted(b.title for b in s.premium)) for s in qs],
      solution="Store.objects.prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.filter(price__gt=55), to_attr='premium'))",
      notes="A filtered prefetch is still one query, and the filter runs in the database - the "
             "rows you did not ask for never reach Python at all.",
      alternatives=(
          ("bad",
           "Store.objects.prefetch_related(Prefetch('books',\n"
           "    queryset=Book.objects.filter(price__gt=55)))",
           "no to_attr, so the filtered books land in s.books.all() and s.premium is missing"),
          ("bad",
           "[(s, [b for b in s.books.all() if b.price and b.price > 55]) for s in Store.objects.all()]",
           "filtering in Python drags every stocked book across, one query per store"),
      )),

    E(slug="pf-count-instead", level="medium", section=S, title="When prefetch is the wrong tool",
      prompt="(lastname, number of books) for authors with pk <= 20, ordered by pk.",
      solution="Author.objects.filter(pk__lte=20).annotate(n=Count('books')).order_by('pk')"
               ".values_list('lastname', 'n')",
      naive="[(a.lastname, a.books.count()) for a in Author.objects.filter(pk__lte=20).order_by('pk')]",
      order_matters=True,
      notes="prefetch_related would drag every book row into memory just to call len() on it. "
            "If you only need the number, count it in the database.",
      alternatives=(
          ("good",
           "Author.objects.filter(pk__lte=20).order_by('pk').annotate(\n"
           "    n=Count('books')).values_list('lastname', 'n')",
           "annotate() before or after order_by() makes no difference to the SQL"),
          ("bad",
           "[(a.lastname, a.books.count()) for a in Author.objects.filter(pk__lte=20)]",
           "a COUNT query per author"),
          ("bad",
           "[(a.lastname, len(a.books.all()))\n"
           " for a in Author.objects.filter(pk__lte=20).prefetch_related('books')]",
           "two queries, but it hauls every book row into memory to count them"),
      )),

    E(slug="pf-sliced", level="hard", section=S, title="Sliced prefetch",
      prompt="Authors with pk <= 10. The grader reads a.recent_books: that author's 3 most recently "
      "published books, newest first, ties broken by the lower id.",
      consume=lambda qs: [(a.lastname, [b.title for b in a.recent_books]) for a in qs],
      solution="Author.objects.filter(pk__lte=10).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.order_by('-published_date', 'id')[:3],\n"
               "             to_attr='recent_books'))",
      hints=["Since Django 4.2 a Prefetch() queryset may be sliced - Django rewrites it with a "
             "window function."],
      notes="Django rewrites a sliced prefetch with a window function so the per-object limit "
             "happens in SQL. Slicing a.books.all()[:3] yourself would have fetched every book "
             "first.",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk__lte=10).prefetch_related(\n"
           "    Prefetch('books', queryset=Book.objects.order_by('-published_date', 'id'),\n"
           "             to_attr='recent_books'))",
           "every book of every author, where the contract wants the three most recent"),
          ("bad",
           "[(a, a.books.order_by('-published_date', 'id')[:3]) for a in\n"
           " Author.objects.filter(pk__lte=10)]",
           "a query per author, and the wrong shape - the grader reads a.recent_books"),
      )),

    E(slug="pf-existing-list", level="hard", section=S, title="prefetch onto objects you already have",
      prompt="The list books is already in memory - 30 Book objects, fetched before the clock "
             "started, exactly as they would arrive from a cache or a serializer. Attach the "
             "reviews of those books without fetching the books again, and return the list.",
      consume=lambda books: [(b.title, len(b.reviews.all())) for b in books],
      setup=_books_in_memory,
      solution="prefetch_related_objects(books, 'reviews')\n"
               "books",
      naive="books",
      order_matters=True,
      hints=["the attaching function returns None, so the answer needs two statements - "
             ":ml lets you type both before anything runs."],
      notes="prefetch_related_objects() is the escape hatch when the objects arrived from "
            "somewhere else - a cache, a serializer, a previous query. You cannot call "
            ".prefetch_related() on a list, and re-querying the books to get one would "
            "defeat the point.",
      alternatives=(
          ("good",
           "prefetch_related_objects(books, 'reviews__book')\n"
           "books",
           "the extra level is free: Django sees those books are already in hand and does not fetch them again"),
          ("bad",
           "books",
           "the list as it arrived - one query per book once the reviews are read"),
          ("bad",
           "Book.objects.order_by('pk').prefetch_related('reviews')[:30]",
           "right, but it throws away the list it was handed and buys the books a second time"),
      )),

    E(slug="pf-generic-fk", level="hard", section=S, title="Generic foreign key",
      prompt="The first 40 TaggedItem rows ordered by object_id then pk - that range covers both tagged "
             "books and tagged authors. The grader reads the tag name and str() of the tagged object.",
      consume=lambda qs: [(ti.tag.name, str(ti.content_object)) for ti in qs],
      solution="TaggedItem.objects.select_related('tag').prefetch_related('content_object')"
               ".order_by('object_id', 'pk')[:40]",
      naive="TaggedItem.objects.select_related('tag').order_by('object_id', 'pk')[:40]",
      order_matters=True,
      notes="select_related cannot follow a GenericForeignKey (the target table is not known at SQL "
            "time); prefetch_related can - one query per content type.",
      alternatives=(
          ("bad",
           "TaggedItem.objects.select_related('tag', 'content_object').order_by('object_id', 'pk')[:40]",
           "select_related cannot follow a GenericForeignKey - the target table is not known at SQL time"),
          ("bad",
           "TaggedItem.objects.select_related('tag').order_by('object_id', 'pk')[:40]",
           "the tag is joined, but each content_object is fetched on its own"),
      )),

    E(slug="pf-two-attrs", level="medium", section=S, title="Two prefetches of one relation",
      prompt="All stores. The grader reads s.empty_stock (stock rows with quantity == 0) and "
      "s.busy_stock (quantity > 25).",
      consume=lambda qs: [(s.name, sorted(x.shelf for x in s.empty_stock), sorted(x.shelf for x in s.busy_stock)) for s in qs],
      solution="Store.objects.prefetch_related(\n"
               "    Prefetch('stock', queryset=StoreStock.objects.filter(quantity=0), to_attr='empty_stock'),\n"
               "    Prefetch('stock', queryset=StoreStock.objects.filter(quantity__gt=25), to_attr='busy_stock'))",
      notes="The same relation can be prefetched twice as long as each one has its own to_attr.",
      alternatives=(
          ("bad",
           "Store.objects.prefetch_related(\n"
           "    Prefetch('stock', queryset=StoreStock.objects.filter(quantity=0),\n"
           "             to_attr='empty_stock'))",
           "only half the question - s.busy_stock never gets set"),
          ("bad",
           "[(s, [x for x in s.stock.all() if x.quantity == 0],\n"
           "     [x for x in s.stock.all() if x.quantity > 25]) for s in Store.objects.all()]",
           "the right two lists, sorted out in Python after a query per store"),
      )),

    E(slug="pf-nested-filtered", level="hard", section=S, title="Nested prefetch inside a Prefetch",
      prompt="Publishers with pk <= 5. For each, only their books priced >= 55, and for each of those "
      "books its reviews.",
      consume=lambda qs: [(p.lastname, sorted((b.title, sorted(r.rating for r in b.reviews.all())) for b in p.books.all())) for p in qs],
      solution="Publisher.objects.filter(pk__lte=5).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.filter(price__gte=55).prefetch_related('reviews')))",
      notes="A Prefetch queryset can prefetch in turn, so each level stays one query however the "
             "filtering is arranged.",
      alternatives=(
          ("good",
           "Publisher.objects.filter(pk__lte=5).prefetch_related(\n"
           "    Prefetch('books', queryset=Book.objects.filter(price__gte=55)), 'books__reviews')",
           "the nested lookup reuses the filtered prefetch above it rather than re-fetching books"),
          ("bad",
           "Publisher.objects.filter(pk__lte=5).prefetch_related(\n"
           "    Prefetch('books', queryset=Book.objects.filter(price__gte=55)))",
           "the books are filtered, then every one of them fetches its own reviews"),
      )),
]
