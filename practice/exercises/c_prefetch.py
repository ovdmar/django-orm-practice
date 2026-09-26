"""prefetch_related(): a second query instead of N, for the multi-valued side."""

from ._base import Exercise as E

S = "prefetch_related"

EXERCISES = [
    E(slug="pf-author-books", section=S, title="Reverse FK",
      prompt="Authors with pk <= 20, each with their books.",
      consume=lambda qs: [(a.lastname, sorted(b.title for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=20).prefetch_related('books')",
      naive="Author.objects.filter(pk__lte=20)",
      notes="select_related cannot do this: a reverse FK is multi-valued, so it needs its own query "
            "(one, not one per author)."),

    E(slug="pf-m2m", section=S, title="Forward M2M",
      prompt="The first 25 books by pk, with their contributors.",
      consume=lambda qs: [(b.title, sorted(a.lastname for a in b.contributors.all())) for b in qs],
      solution="Book.objects.prefetch_related('contributors').order_by('pk')[:25]",
      naive="Book.objects.order_by('pk')[:25]",
      order_matters=True),

    E(slug="pf-reverse-m2m", section=S, title="Reverse M2M",
      prompt="The first 15 users by pk, with the authors they follow.",
      consume=lambda qs: [(u.username, sorted(a.lastname for a in u.following.all())) for u in qs],
      solution="User.objects.prefetch_related('following').order_by('pk')[:15]",
      naive="User.objects.order_by('pk')[:15]",
      order_matters=True),

    E(slug="pf-to-attr", section=S, title="Prefetch(to_attr=…)",
      prompt="Authors with pk <= 25. The grader reads a.expensive_books, which must hold only that "
      "author's books priced >= 50.",
      consume=lambda qs: [(a.lastname, sorted(b.title for b in a.expensive_books)) for a in qs],
      solution="Author.objects.filter(pk__lte=25).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.filter(price__gte=50), to_attr='expensive_books'))",
      hints=["Prefetch(lookup, queryset=…, to_attr=…) - with to_attr the result is a plain list, "
             "not a manager."],
      notes="to_attr keeps the filtered set separate from a.books.all(), which would otherwise be "
            "cached with a *filtered* meaning and surprise the next reader."),

    E(slug="pf-nested", section=S, title="Nested prefetch",
      prompt="Authors with pk <= 15, their books, and each book's reviews.",
      consume=lambda qs: [(a.lastname, sorted((b.title, sorted(r.rating for r in b.reviews.all())) for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=15).prefetch_related('books__reviews')",
      naive="Author.objects.filter(pk__lte=15)",
      notes="One query per level, regardless of how many rows each level has."),

    E(slug="pf-with-select-related", section=S, title="select_related inside a prefetch",
      prompt="Authors with pk <= 20 and their books, where the grader also reads each book's publisher.",
      consume=lambda qs: [(a.lastname, sorted((b.title, b.publisher.lastname) for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=20).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.select_related('publisher')))",
      naive="Author.objects.filter(pk__lte=20).prefetch_related('books')",
      notes="The prefetch queryset is a normal queryset - give it its own select_related and the second "
            "level comes back joined."),

    E(slug="pf-mixed", section=S, title="select_related and prefetch_related together",
      prompt="The first 30 books by pk, with their publisher and their tags (a generic relation).",
      consume=lambda qs: [(b.title, b.publisher.lastname, sorted(t.tag.name for t in b.tags.all())) for b in qs],
      solution="Book.objects.select_related('publisher').prefetch_related('tags__tag').order_by('pk')[:30]",
      naive="Book.objects.select_related('publisher').order_by('pk')[:30]",
      order_matters=True),

    E(slug="pf-through", section=S, title="Prefetch the through model",
      prompt="Stores with pk <= 3, and their stock rows - the grader reads each row's book and quantity.",
      consume=lambda qs: [(s.name, sorted((x.book.title, x.quantity) for x in s.stock.all())) for s in qs],
      solution="Store.objects.filter(pk__lte=3).prefetch_related(\n"
               "    Prefetch('stock', queryset=StoreStock.objects.select_related('book')))",
      naive="Store.objects.filter(pk__lte=3).prefetch_related('stock')",
      notes="store.books.all() hides the through row. When you need quantity/shelf you must go through "
            "StoreStock yourself."),

    E(slug="pf-filtered-m2m", section=S, title="Filtered M2M prefetch",
      prompt="All stores. The grader reads s.premium: the books that store stocks priced > 55.",
      consume=lambda qs: [(s.name, sorted(b.title for b in s.premium)) for s in qs],
      solution="Store.objects.prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.filter(price__gt=55), to_attr='premium'))"),

    E(slug="pf-count-instead", section=S, title="When prefetch is the wrong tool",
      prompt="(lastname, number of books) for authors with pk <= 20, ordered by pk.",
      solution="Author.objects.filter(pk__lte=20).annotate(n=Count('books')).order_by('pk')"
               ".values_list('lastname', 'n')",
      naive="[(a.lastname, a.books.count()) for a in Author.objects.filter(pk__lte=20).order_by('pk')]",
      order_matters=True,
      notes="prefetch_related would drag every book row into memory just to call len() on it. "
            "If you only need the number, count it in the database."),

    E(slug="pf-sliced", section=S, title="Sliced prefetch",
      prompt="Authors with pk <= 10. The grader reads a.recent_books: that author's 3 most recently "
      "published books, ordered by -published_date then id.",
      consume=lambda qs: [(a.lastname, [b.title for b in a.recent_books]) for a in qs],
      solution="Author.objects.filter(pk__lte=10).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.order_by('-published_date', 'id')[:3],\n"
               "             to_attr='recent_books'))",
      hints=["Since Django 4.2 a Prefetch() queryset may be sliced - Django rewrites it with a "
             "window function."]),

    E(slug="pf-existing-list", section=S, title="prefetch onto objects you already have",
      prompt="books = list(Book.objects.order_by('pk')[:30]) is already in memory. Attach the reviews of "
      "those books without fetching the books again, and return the list.",
      consume=lambda books: [(b.title, len(b.reviews.all())) for b in books],
      solution="books = list(Book.objects.order_by('pk')[:30])\n"
               "prefetch_related_objects(books, 'reviews')\n"
               "books",
      naive="list(Book.objects.order_by('pk')[:30])",
      order_matters=True,
      notes="prefetch_related_objects() is the escape hatch when the objects arrived from somewhere "
            "else - a cache, a serializer, a previous query."),

    E(slug="pf-generic-fk", section=S, title="Generic foreign key",
      prompt="The first 40 TaggedItem rows ordered by object_id then pk - that range covers both tagged "
             "books and tagged authors. The grader reads the tag name and str() of the tagged object.",
      consume=lambda qs: [(ti.tag.name, str(ti.content_object)) for ti in qs],
      solution="TaggedItem.objects.select_related('tag').prefetch_related('content_object')"
               ".order_by('object_id', 'pk')[:40]",
      naive="TaggedItem.objects.select_related('tag').order_by('object_id', 'pk')[:40]",
      order_matters=True,
      notes="select_related cannot follow a GenericForeignKey (the target table is not known at SQL "
            "time); prefetch_related can - one query per content type."),

    E(slug="pf-two-attrs", section=S, title="Two prefetches of one relation",
      prompt="All stores. The grader reads s.empty_stock (stock rows with quantity == 0) and "
      "s.busy_stock (quantity > 25).",
      consume=lambda qs: [(s.name, sorted(x.shelf for x in s.empty_stock), sorted(x.shelf for x in s.busy_stock)) for s in qs],
      solution="Store.objects.prefetch_related(\n"
               "    Prefetch('stock', queryset=StoreStock.objects.filter(quantity=0), to_attr='empty_stock'),\n"
               "    Prefetch('stock', queryset=StoreStock.objects.filter(quantity__gt=25), to_attr='busy_stock'))",
      notes="The same relation can be prefetched twice as long as each one has its own to_attr."),

    E(slug="pf-nested-filtered", section=S, title="Nested prefetch inside a Prefetch",
      prompt="Publishers with pk <= 5. For each, only their books priced >= 55, and for each of those "
      "books its reviews.",
      consume=lambda qs: [(p.lastname, sorted((b.title, sorted(r.rating for r in b.reviews.all())) for b in p.books.all())) for p in qs],
      solution="Publisher.objects.filter(pk__lte=5).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.filter(price__gte=55).prefetch_related('reviews')))"),
]
