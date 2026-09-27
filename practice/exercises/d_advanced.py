"""Beyond the two big hammers: annotate, Subquery, windows, conditional aggregates."""

from ._base import Exercise as E

S = "advanced"

EXERCISES = [
    E(slug="ad-publisher-stats", level="medium", section=S, title="Group by with two aggregates",
      prompt="(lastname, number of books, average book price) for every publisher, ordered by pk.",
      solution="Publisher.objects.annotate(n=Count('books'), a=Avg('books__price')).order_by('pk')"
               ".values_list('lastname', 'n', 'a')",
      order_matters=True,
      notes="annotate() over a join groups by the outer model's primary key, so every aggregate "
             "in the same call is computed in that one GROUP BY pass.",
      alternatives=(
          ("careful",
           "Publisher.objects.order_by('pk').values_list('lastname').annotate(\n"
           "    n=Count('books'), a=Avg('books__price'))",
           "values_list() before annotate() groups by lastname rather than by pk - the same numbers here only because no two publishers share a lastname"),
          ("bad",
           "[(p.lastname, p.books.count(),\n"
           "  p.books.aggregate(a=Avg('price'))['a']) for p in Publisher.objects.all()]",
           "two queries per publisher, 41 in total"),
      )),

    E(slug="ad-count-distinct", level="hard", section=S, title="The double-join multiplication trap",
      prompt="(lastname, number of books, number of followers) for authors with pk <= 15, ordered by pk. "
      "The numbers must all be right.",
      solution="Author.objects.filter(pk__lte=15).annotate(nb=Count('books', distinct=True),\n"
               "                                           nf=Count('followers', distinct=True))"
               ".order_by('pk').values_list('lastname', 'nb', 'nf')",
      naive=None,
      hints=["Two multi-valued joins in one query produce a cartesian product of rows."],
      notes="Without distinct=True you get books*followers rows, so each count is multiplied by the "
            "other. Same query count, wrong answer - the failure mode annotate() is famous for.",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk__lte=15).annotate(\n"
           "    nb=Count('books'), nf=Count('followers')).order_by('pk').values_list(\n"
           "        'lastname', 'nb', 'nf')",
           "one query, wrong numbers: the two joins multiply, so each count comes back as itself times the other's row count"),
          ("bad",
           "[(a.lastname, a.books.count(), a.followers.count())\n"
           " for a in Author.objects.filter(pk__lte=15).order_by('pk')]",
           "right numbers, 31 queries - two COUNTs per author"),
      )),

    E(slug="ad-subquery-latest", level="hard", section=S, title="Subquery + OuterRef",
      prompt="For books with pk <= 20, ordered by pk: (title, username of the reviewer who left the most "
      "recent review - latest created, ties broken by highest pk - or None).",
      solution="latest = Review.objects.filter(book=OuterRef('pk')).order_by('-created', '-pk')\n"
               "Book.objects.filter(pk__lte=20).annotate(u=Subquery(latest.values('user__username')[:1]))\\\n"
               "    .order_by('pk').values_list('title', 'u')",
      naive="[(b.title, (r := b.reviews.order_by('-created', '-pk').first()) and r.user.username)\n"
            " for b in Book.objects.filter(pk__lte=20).order_by('pk')]",
      order_matters=True,
      hints=["OuterRef('pk') refers to the outer row; slice the subquery to [:1] so it returns one value."],
      notes="A correlated subquery is evaluated per outer row by the database, but it travels as "
             "one statement. Slicing it to [:1] is what makes it a single value Django can "
             "select.",
      alternatives=(
          ("bad",
           "[(b.title, (r := b.reviews.order_by('-created', '-pk').first()) and r.user.username)\n"
           " for b in Book.objects.filter(pk__lte=20).order_by('pk')]",
           "two queries per book - one for its latest review, one for that reviewer"),
          ("bad",
           "Book.objects.filter(pk__lte=20).annotate(\n"
           "    u=Max('reviews__user__username')).order_by('pk').values_list('title', 'u')",
           "MAX over the usernames is the alphabetically last reviewer, not the most recent one"),
      )),

    E(slug="ad-exists", level="medium", section=S, title="Exists()",
      prompt="Author objects who have at least one book carrying a 5-star review. No duplicated rows.",
      solution="Author.objects.filter(Exists(Review.objects.filter(rating=5, book__author=OuterRef('pk'))))",
      notes="filter(books__reviews__rating=5).distinct() also works, but Exists() stops at the first "
            "match and needs no DISTINCT over the whole row.",
      alternatives=(
          ("good",
           "Author.objects.filter(books__reviews__rating=5).distinct()",
           "a join plus DISTINCT over the whole row; Exists() stops at the first match instead and needs no de-duplication"),
          ("bad",
           "Author.objects.filter(books__reviews__rating=5)",
           "no distinct(), so an author with several 5-star reviews arrives several times"),
      )),

    E(slug="ad-window", level="hard", section=S, title="Window function",
      prompt="The most expensive book per genre: (genre, title, price), ordered by genre. Books without "
      "a price are out.",
      solution="ranked = Book.objects.filter(price__isnull=False).annotate(\n"
               "    r=Window(RowNumber(), partition_by='genre', order_by=['-price', 'id']))\n"
               "ranked.filter(r=1).order_by('genre').values_list('genre', 'title', 'price')",
      order_matters=True,
      hints=["Window(RowNumber(), partition_by=…, order_by=…); since Django 4.2 you can filter on the "
             "window annotation and Django wraps it in a subquery."],
      notes="A window function computes a value per row over a partition without collapsing the "
             "rows, which is what makes best-per-group possible at all. Django wraps the query in "
             "a subquery so the window result can be filtered.",
      alternatives=(
          ("bad",
           "Book.objects.filter(price__isnull=False).order_by('genre', '-price', 'id').distinct(\n"
           "    'genre').values_list('genre', 'title', 'price')",
           "DISTINCT ON is PostgreSQL only - SQLite raises NotSupportedError"),
          ("bad",
           "[(g, *Book.objects.filter(genre=g, price__isnull=False).order_by(\n"
           "    '-price', 'id').values_list('title', 'price').first())\n"
           " for g in sorted(Book.objects.values_list('genre', flat=True).distinct())]",
           "a query per genre on top of the one that lists them"),
      )),

    E(slug="ad-units-sold", level="medium", section=S, title="Sum across a reverse FK",
      prompt="The 10 best selling books: (title, total quantity ordered), highest quantity first, ties "
      "broken by the lower id. Books that were never ordered are out.",
      solution="Book.objects.annotate(sold=Sum('order_items__quantity')).exclude(sold=None)"
               ".order_by('-sold', 'id').values_list('title', 'sold')[:10]",
      order_matters=True,
      notes="Sum over a reverse FK joins and groups. Dropping the NULL sums is how you say you "
             "only want books that actually sold - the aggregate equivalent of an inner join.",
      alternatives=(
          ("good",
           "Book.objects.annotate(sold=Sum('order_items__quantity')).filter(\n"
           "    sold__isnull=False).order_by('-sold', 'id').values_list('title', 'sold')[:10]",
           "filter(sold__isnull=False) and exclude(sold=None) compile to the same HAVING"),
          ("bad",
           "Book.objects.annotate(sold=Count('order_items__quantity')).exclude(sold=None).order_by('-sold', 'id').values_list('title', 'sold')[:10]",
           "COUNT is how many order lines there were, not how many copies they were for"),
      )),

    E(slug="ad-annotate-and-prefetch", level="medium", section=S, title="annotate + prefetch in two queries",
      prompt="Authors with pk <= 12. The grader reads a.nb (their book count) and their books.",
      consume=lambda qs: [(a.lastname, a.nb, sorted(b.title for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=12).annotate(nb=Count('books')).prefetch_related('books')",
      notes="The annotation rides along on the first query and costs nothing extra. The prefetch "
             "is the second query, exactly as it would have been on its own.",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk__lte=12).prefetch_related('books')",
           "the books arrive, but a.nb was never annotated, so the grader finds no such attribute"),
          ("bad",
           "[a for a in Author.objects.filter(pk__lte=12).annotate(nb=Count('books'))]",
           "the count comes free with the first query; the books then cost one query each"),
      )),

    E(slug="ad-conditional-count", level="hard", section=S, title="Conditional aggregation",
      prompt="For publishers with pk <= 10, ordered by pk: (lastname, #books under 20, #books from 20 to "
      "40 inclusive, #books over 40). Books without a price count in none of them.",
      solution="Publisher.objects.filter(pk__lte=10).annotate(\n"
               "    cheap=Count('books', filter=Q(books__price__lt=20)),\n"
               "    mid=Count('books', filter=Q(books__price__gte=20, books__price__lte=40)),\n"
               "    dear=Count('books', filter=Q(books__price__gt=40)),\n"
               ").order_by('pk').values_list('lastname', 'cheap', 'mid', 'dear')",
      order_matters=True,
      hints=["Aggregates take a filter= argument: Count('books', filter=Q(...))."],
      notes="filter= inside an aggregate becomes a FILTER (or CASE) clause, so several "
             "differently-filtered counts share one scan of the same join instead of one query "
             "each.",
      alternatives=(
          ("good",
           "Publisher.objects.filter(pk__lte=10).annotate(\n"
           "    cheap=Count(Case(When(books__price__lt=20, then=1))),\n"
           "    mid=Count(Case(When(books__price__gte=20, books__price__lte=40, then=1))),\n"
           "    dear=Count(Case(When(books__price__gt=40, then=1)))).order_by('pk').values_list(\n"
           "        'lastname', 'cheap', 'mid', 'dear')",
           "Case/When is what filter= compiles down to - the older spelling of the same query"),
          ("bad",
           "[(p.lastname, p.books.filter(price__lt=20).count(),\n"
           "  p.books.filter(price__gte=20, price__lte=40).count(),\n"
           "  p.books.filter(price__gt=40).count()) for p in Publisher.objects.filter(pk__lte=10)]",
           "three COUNT queries per publisher - 31 in total for one scan's worth of work"),
      )),

    E(slug="ad-avg-by-genre", level="medium", section=S, title="Group by a joined column",
      prompt="Average review rating per book genre: (genre, average rating), ordered by genre.",
      solution="Review.objects.values('book__genre').annotate(a=Avg('rating')).order_by('book__genre')"
               ".values_list('book__genre', 'a')",
      order_matters=True,
      notes="values() before annotate() sets the GROUP BY; the trailing values_list() only picks the "
            "output columns.",
      alternatives=(
          ("careful",
           "Book.objects.order_by('genre').values_list('genre').annotate(\n"
           "    a=Avg('reviews__rating'))",
           "grouping from the book side answers a slightly different question - it would also list a genre whose books have no reviews at all, with None"),
          ("bad",
           "{g: Review.objects.filter(book__genre=g).aggregate(a=Avg('rating'))['a']\n"
           "  for g in sorted(Book.objects.values_list('genre', flat=True).distinct())}",
           "a dict where tuples were asked for, and a query per genre to build it"),
      )),

    E(slug="ad-filtered-relation", level="medium", section=S, title="Aggregate only part of a relation",
      prompt="For authors with pk <= 15, ordered by pk: (lastname, total price of their fantasy books "
      "only, or None).",
      solution="Author.objects.filter(pk__lte=15).annotate(\n"
               "    t=Sum('books__price', filter=Q(books__genre='fantasy'))\n"
               ").order_by('pk').values_list('lastname', 't')",
      order_matters=True,
      notes="FilteredRelation('books', condition=Q(books__genre='fantasy')) is the heavier alternative - "
            "it is what you need when several aggregates must share one filtered join.",
      alternatives=(
          ("good",
           "Author.objects.filter(pk__lte=15).annotate(\n"
           "    f=FilteredRelation('books', condition=Q(books__genre='fantasy'))).annotate(\n"
           "        t=Sum('f__price')).order_by('pk').values_list('lastname', 't')",
           "FilteredRelation puts the condition in the JOIN itself, which is what you need when several aggregates must share one filtered join"),
          ("bad",
           "Author.objects.filter(pk__lte=15, books__genre='fantasy').annotate(\n"
           "    t=Sum('books__price')).order_by('pk').values_list('lastname', 't')",
           "filtering in the WHERE drops the authors with no fantasy book instead of showing them with None"),
      )),

    E(slug="ad-in-bulk", level="easy", section=S, title="in_bulk()",
      prompt="For ids = list(range(3, 200, 7)), return {book id: title} for the books that exist.",
      solution="ids = list(range(3, 200, 7))\n"
               "{pk: b.title for pk, b in Book.objects.in_bulk(ids).items()}",
      naive="{pk: Book.objects.get(pk=pk).title for pk in range(3, 200, 7)}",
      notes="in_bulk() is the pk-keyed dict you were about to build by hand.",
      alternatives=(
          ("good",
           "dict(Book.objects.filter(pk__in=list(range(3, 200, 7))).values_list('id', 'title'))",
           "one query too, and it never builds a model instance - in_bulk() gives you whole objects"),
          ("bad",
           "{pk: Book.objects.get(pk=pk).title for pk in range(3, 200, 7)}",
           "a query per id, and DoesNotExist the moment one is missing"),
      )),

    E(slug="ad-update-f", level="medium", section=S, title="update() with F()", mutates=True,
      prompt="Raise the price of every priced book of publisher pk=1 by 5, without loading a single book "
      "into Python, then return the new total price of that publisher's books.",
      solution="Book.objects.filter(publisher_id=1, price__isnull=False).update(price=F('price') + 5)\n"
               "Book.objects.filter(publisher_id=1).aggregate(t=Sum('price'))['t']",
      naive="for b in Book.objects.filter(publisher_id=1, price__isnull=False):\n"
            "    b.price += 5\n"
            "    b.save()\n"
            "Book.objects.filter(publisher_id=1).aggregate(t=Sum('price'))['t']",
      notes="F() keeps the arithmetic in SQL: one UPDATE for the whole set, and no read-modify-write "
            "race with other writers.",
      alternatives=(
          ("careful",
           "Book.objects.filter(publisher_id=1).update(price=F('price') + 5)\n"
           "Book.objects.filter(publisher_id=1).aggregate(t=Sum('price'))['t']",
           "right here only because NULL + 5 is NULL, so the unpriced books stay untouched and the sum is unaffected - on a column where NULL meant zero this would quietly lose rows"),
          ("bad",
           "for b in Book.objects.filter(publisher_id=1, price__isnull=False):\n"
           "    b.price += 5\n"
           "    b.save()\n"
           "Book.objects.filter(publisher_id=1).aggregate(t=Sum('price'))['t']",
           "an UPDATE per book, and a read-modify-write another writer can interleave with"),
      )),

    E(slug="ad-correlated-avg", level="hard", section=S, title="Correlated subquery",
      prompt="How many books cost strictly more than the average price of their own publisher's books? "
      "Return the number.",
      solution="avg = (Book.objects.filter(publisher=OuterRef('publisher')).values('publisher')\n"
               "       .annotate(a=Avg('price')).values('a'))\n"
               "Book.objects.annotate(pa=Subquery(avg)).filter(price__gt=F('pa')).count()",
      hints=["Group the subquery by the outer publisher with .values('publisher').annotate(...)."],
      notes="Comparing a row against an aggregate of its own group needs that aggregate as a "
             "subquery. A plain annotate would group the outer query too, and you would be "
             "comparing something else.",
      alternatives=(
          ("good",
           "Book.objects.annotate(pa=Avg('publisher__books__price')).filter(\n"
           "    price__gt=F('pa')).count()",
           "the average over the publisher's books reached by walking back down the relation - the GROUP BY is still the book, so it is the same comparison in one query"),
          ("bad",
           "sum(1 for b in Book.objects.select_related('publisher')\n"
           "    if b.price and b.price > b.publisher.books.aggregate(a=Avg('price'))['a'])",
           "an AVG query per book - 701 of them"),
      )),

    E(slug="ad-two-hops", level="easy", section=S, title="Two hops on a self FK",
      prompt="Author objects who were recommended by someone who was themselves recommended by author "
      "pk=1.",
      solution="Author.objects.filter(recommendedby__recommendedby_id=1)",
      notes="Every __ hop is a JOIN, a self join included - Django just aliases the table again. "
             "Two hops is still one query.",
      alternatives=(
          ("good",
           "Author.objects.filter(recommendedby__in=Author.objects.filter(recommendedby_id=1))",
           "a subquery instead of a second JOIN - one query either way"),
          ("bad",
           "[a for r in Author.objects.filter(recommendedby_id=1) for a in r.recommended.all()]",
           "a query per author recommended by author 1"),
      )),

    E(slug="ad-annotated-prefetch", level="medium", section=S, title="Annotation inside a prefetch",
      prompt="Publishers with pk <= 5 and all their books; the grader reads b.nrev, the number of "
      "reviews of each book.",
      consume=lambda qs: [(p.lastname, sorted((b.title, b.nrev) for b in p.books.all())) for p in qs],
      solution="Publisher.objects.filter(pk__lte=5).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.annotate(nrev=Count('reviews'))))",
      notes="The prefetch queryset is a real queryset: annotations, filters and ordering on it "
             "shape the inner query, and the outer one never needs to know.",
      alternatives=(
          ("bad",
           "Publisher.objects.filter(pk__lte=5).prefetch_related('books')",
           "the books arrive without nrev, so the grader finds no such attribute"),
          ("bad",
           "Publisher.objects.filter(pk__lte=5).prefetch_related('books__reviews')",
           "three queries and still no nrev - the reviews are fetched, not counted"),
      )),

    E(slug="ad-coalesce", level="medium", section=S, title="Coalesce in the database",
      prompt="(title, price or 0 when the price is NULL) for books with pk <= 30, ordered by pk. The "
      "substitution must happen in SQL.",
      solution="Book.objects.filter(pk__lte=30).annotate(p=Coalesce('price', Value(0)))"
               ".order_by('pk').values_list('title', 'p')",
      order_matters=True,
      notes="Substituting in SQL keeps the value available to ORDER BY, to filters and to "
             "further aggregates. Doing it in Python afterwards puts it out of the database's "
             "reach.",
      alternatives=(
          ("good",
           "Book.objects.filter(pk__lte=30).annotate(p=Coalesce('price', 0)).order_by(\n"
           "    'pk').values_list('title', 'p')",
           "a bare 0 works - Django wraps it in Value() for you once it knows the field type"),
          ("good",
           "Book.objects.filter(pk__lte=30).annotate(\n"
           "    p=Case(When(price__isnull=True, then=Value(0)), default='price')).order_by(\n"
           "        'pk').values_list('title', 'p')",
           "Case/When spells out what Coalesce says in one word"),
          ("careful",
           "[(b.title, b.price or 0) for b in Book.objects.filter(pk__lte=30).order_by('pk')]",
           "one query, but the substitution happens in Python - out of reach of ORDER BY, of filters and of any aggregate that would build on it"),
          ("bad",
           "Book.objects.filter(pk__lte=30).annotate(p=Coalesce('price', Value(0))).order_by(\n"
           "    'pk').values_list('title', 'price')",
           "p is computed and then thrown away - the selected column is still the NULL-bearing price"),
      )),

    E(slug="ad-count-two-levels", level="hard", section=S, title="Counting two levels down",
      prompt="For authors with pk <= 10, ordered by pk: (lastname, number of their books, number of "
      "reviews across all their books). Both numbers must be right.",
      solution="Author.objects.filter(pk__lte=10).annotate(\n"
               "    nb=Count('books', distinct=True), nr=Count('books__reviews')\n"
               ").order_by('pk').values_list('lastname', 'nb', 'nr')",
      order_matters=True,
      notes="The join fans out one row per review, so the book count needs distinct=True while the "
            "review count - the leaf of the join - must NOT have it.",
      alternatives=(
          ("careful",
           "Author.objects.filter(pk__lte=10).annotate(\n"
           "    nb=Count('books', distinct=True),\n"
           "    nr=Count('books__reviews', distinct=True)).order_by('pk').values_list(\n"
           "        'lastname', 'nb', 'nr')",
           "the same numbers, because review ids are unique anyway - so the DISTINCT on the leaf is sorting work the database did not need to do"),
          ("bad",
           "Author.objects.filter(pk__lte=10).annotate(\n"
           "    nb=Count('books'), nr=Count('books__reviews')).order_by('pk').values_list(\n"
           "        'lastname', 'nb', 'nr')",
           "the join fans out one row per review, so without distinct=True the book count is multiplied by it"),
      )),

    E(slug="ad-union", level="medium", section=S, title="union()",
      prompt="A flat list of the lastnames that occur either as an author lastname or as a publisher "
      "lastname, each one listed once.",
      solution="Author.objects.values_list('lastname', flat=True).order_by().union(\n"
               "    Publisher.objects.values_list('lastname', flat=True).order_by())",
      naive="set(Author.objects.values_list('lastname', flat=True)) | "
            "set(Publisher.objects.values_list('lastname', flat=True))",
      hints=["Both models have a Meta.ordering, and SQLite refuses ORDER BY inside a compound "
             "statement - clear it with .order_by()."],
      notes="SQL UNION already de-duplicates; union(..., all=True) if you want the duplicates.",
      alternatives=(
          ("bad",
           "sorted(set(Author.objects.values_list('lastname', flat=True))\n"
           "       | set(Publisher.objects.values_list('lastname', flat=True)))",
           "the same answer for two queries and both tables pulled into memory"),
          ("bad",
           "Author.objects.values_list('lastname', flat=True).union(\n"
           "    Publisher.objects.values_list('lastname', flat=True))",
           "both models carry a Meta.ordering, and SQLite refuses ORDER BY inside a compound statement - clear it with order_by()"),
      )),
]
