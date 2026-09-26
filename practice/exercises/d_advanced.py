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
             "in the same call is computed in that one GROUP BY pass."),

    E(slug="ad-count-distinct", level="hard", section=S, title="The double-join multiplication trap",
      prompt="(lastname, number of books, number of followers) for authors with pk <= 15, ordered by pk. "
      "The numbers must all be right.",
      solution="Author.objects.filter(pk__lte=15).annotate(nb=Count('books', distinct=True),\n"
               "                                           nf=Count('followers', distinct=True))"
               ".order_by('pk').values_list('lastname', 'nb', 'nf')",
      naive=None,
      hints=["Two multi-valued joins in one query produce a cartesian product of rows."],
      notes="Without distinct=True you get books*followers rows, so each count is multiplied by the "
            "other. Same query count, wrong answer - the failure mode annotate() is famous for."),

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
             "select."),

    E(slug="ad-exists", level="medium", section=S, title="Exists()",
      prompt="Author objects who have at least one book carrying a 5-star review. No duplicated rows.",
      solution="Author.objects.filter(Exists(Review.objects.filter(rating=5, book__author=OuterRef('pk'))))",
      notes="filter(books__reviews__rating=5).distinct() also works, but Exists() stops at the first "
            "match and needs no DISTINCT over the whole row."),

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
             "a subquery so the window result can be filtered."),

    E(slug="ad-units-sold", level="medium", section=S, title="Sum across a reverse FK",
      prompt="The 10 best selling books: (title, total quantity ordered), ordered by -quantity then id. "
      "Books that were never ordered are out.",
      solution="Book.objects.annotate(sold=Sum('order_items__quantity')).exclude(sold=None)"
               ".order_by('-sold', 'id').values_list('title', 'sold')[:10]",
      order_matters=True,
      notes="Sum over a reverse FK joins and groups. Dropping the NULL sums is how you say you "
             "only want books that actually sold - the aggregate equivalent of an inner join."),

    E(slug="ad-annotate-and-prefetch", level="medium", section=S, title="annotate + prefetch in two queries",
      prompt="Authors with pk <= 12. The grader reads a.nb (their book count) and their books.",
      consume=lambda qs: [(a.lastname, a.nb, sorted(b.title for b in a.books.all())) for a in qs],
      solution="Author.objects.filter(pk__lte=12).annotate(nb=Count('books')).prefetch_related('books')",
      notes="The annotation rides along on the first query and costs nothing extra. The prefetch "
             "is the second query, exactly as it would have been on its own."),

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
             "each."),

    E(slug="ad-avg-by-genre", level="medium", section=S, title="Group by a joined column",
      prompt="Average review rating per book genre: (genre, average rating), ordered by genre.",
      solution="Review.objects.values('book__genre').annotate(a=Avg('rating')).order_by('book__genre')"
               ".values_list('book__genre', 'a')",
      order_matters=True,
      notes="values() before annotate() sets the GROUP BY; the trailing values_list() only picks the "
            "output columns."),

    E(slug="ad-filtered-relation", level="medium", section=S, title="Aggregate only part of a relation",
      prompt="For authors with pk <= 15, ordered by pk: (lastname, total price of their fantasy books "
      "only, or None).",
      solution="Author.objects.filter(pk__lte=15).annotate(\n"
               "    t=Sum('books__price', filter=Q(books__genre='fantasy'))\n"
               ").order_by('pk').values_list('lastname', 't')",
      order_matters=True,
      notes="FilteredRelation('books', condition=Q(books__genre='fantasy')) is the heavier alternative - "
            "it is what you need when several aggregates must share one filtered join."),

    E(slug="ad-in-bulk", level="easy", section=S, title="in_bulk()",
      prompt="For ids = list(range(3, 200, 7)), return {book id: title} for the books that exist.",
      solution="ids = list(range(3, 200, 7))\n"
               "{pk: b.title for pk, b in Book.objects.in_bulk(ids).items()}",
      naive="{pk: Book.objects.get(pk=pk).title for pk in range(3, 200, 7)}",
      notes="in_bulk() is the pk-keyed dict you were about to build by hand."),

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
            "race with other writers."),

    E(slug="ad-correlated-avg", level="hard", section=S, title="Correlated subquery",
      prompt="How many books cost strictly more than the average price of their own publisher's books? "
      "Return the number.",
      solution="avg = (Book.objects.filter(publisher=OuterRef('publisher')).values('publisher')\n"
               "       .annotate(a=Avg('price')).values('a'))\n"
               "Book.objects.annotate(pa=Subquery(avg)).filter(price__gt=F('pa')).count()",
      hints=["Group the subquery by the outer publisher with .values('publisher').annotate(...)."],
      notes="Comparing a row against an aggregate of its own group needs that aggregate as a "
             "subquery. A plain annotate would group the outer query too, and you would be "
             "comparing something else."),

    E(slug="ad-two-hops", level="easy", section=S, title="Two hops on a self FK",
      prompt="Author objects who were recommended by someone who was themselves recommended by author "
      "pk=1.",
      solution="Author.objects.filter(recommendedby__recommendedby_id=1)",
      notes="Every __ hop is a JOIN, a self join included - Django just aliases the table again. "
             "Two hops is still one query."),

    E(slug="ad-annotated-prefetch", level="medium", section=S, title="Annotation inside a prefetch",
      prompt="Publishers with pk <= 5 and all their books; the grader reads b.nrev, the number of "
      "reviews of each book.",
      consume=lambda qs: [(p.lastname, sorted((b.title, b.nrev) for b in p.books.all())) for p in qs],
      solution="Publisher.objects.filter(pk__lte=5).prefetch_related(\n"
               "    Prefetch('books', queryset=Book.objects.annotate(nrev=Count('reviews'))))",
      notes="The prefetch queryset is a real queryset: annotations, filters and ordering on it "
             "shape the inner query, and the outer one never needs to know."),

    E(slug="ad-coalesce", level="medium", section=S, title="Coalesce in the database",
      prompt="(title, price or 0 when the price is NULL) for books with pk <= 30, ordered by pk. The "
      "substitution must happen in SQL.",
      solution="Book.objects.filter(pk__lte=30).annotate(p=Coalesce('price', Value(0)))"
               ".order_by('pk').values_list('title', 'p')",
      order_matters=True,
      notes="Substituting in SQL keeps the value available to ORDER BY, to filters and to "
             "further aggregates. Doing it in Python afterwards puts it out of the database's "
             "reach."),

    E(slug="ad-count-two-levels", level="hard", section=S, title="Counting two levels down",
      prompt="For authors with pk <= 10, ordered by pk: (lastname, number of their books, number of "
      "reviews across all their books). Both numbers must be right.",
      solution="Author.objects.filter(pk__lte=10).annotate(\n"
               "    nb=Count('books', distinct=True), nr=Count('books__reviews')\n"
               ").order_by('pk').values_list('lastname', 'nb', 'nr')",
      order_matters=True,
      notes="The join fans out one row per review, so the book count needs distinct=True while the "
            "review count - the leaf of the join - must NOT have it."),

    E(slug="ad-union", level="medium", section=S, title="union()",
      prompt="A flat list of the lastnames that occur either as an author lastname or as a publisher "
      "lastname, each one listed once.",
      solution="Author.objects.values_list('lastname', flat=True).order_by().union(\n"
               "    Publisher.objects.values_list('lastname', flat=True).order_by())",
      naive="set(Author.objects.values_list('lastname', flat=True)) | "
            "set(Publisher.objects.values_list('lastname', flat=True))",
      hints=["Both models have a Meta.ordering, and SQLite refuses ORDER BY inside a compound "
             "statement - clear it with .order_by()."],
      notes="SQL UNION already de-duplicates; union(..., all=True) if you want the duplicates."),
]
