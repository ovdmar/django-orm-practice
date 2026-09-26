"""select_related(): one JOIN instead of N follow-up queries.

Every exercise here shows you the exact code the grader uses to consume your
result, so you know which related objects will be touched.
"""

from ._base import Exercise as E

S = "select_related"

EXERCISES = [
    E(slug="sr-cheapest-books", level="easy", section=S, title="The classic N+1",
      prompt="The 20 cheapest books that have a price, ordered by price then id.",
      consume=lambda qs: [(b.title, b.publisher.lastname) for b in qs],
      solution="Book.objects.filter(price__isnull=False).select_related('publisher')"
               ".order_by('price', 'id')[:20]",
      naive="Book.objects.filter(price__isnull=False).order_by('price', 'id')[:20]",
      order_matters=True,
      notes="Without select_related each b.publisher is its own SELECT: 1 + 20 queries."),

    E(slug="sr-review-chain", level="medium", section=S, title="Two levels deep",
      prompt="The 30 most upvoted reviews, highest upvotes first, ties broken by the lower id. Some "
      "books have no author.",
      consume=lambda qs: [(r.rating, r.book.title, r.book.author and r.book.author.lastname, r.book.publisher.country) for r in qs],
      solution="Review.objects.select_related('book__author', 'book__publisher')"
               ".order_by('-upvotes', 'id')[:30]",
      naive="Review.objects.order_by('-upvotes', 'id')[:30]",
      order_matters=True,
      hints=["Chain relations with __ : select_related('book__author')."],
      notes="A nullable FK becomes a LEFT OUTER JOIN - still one query."),

    E(slug="sr-reverse-o2o", level="medium", section=S, title="Reverse one-to-one",
      prompt="Authors with pk <= 40. Not every author has a profile, so the grader uses hasattr().",
      consume=lambda qs: [(a.lastname, a.profile.website if hasattr(a, 'profile') else None) for a in qs],
      solution="Author.objects.select_related('profile').filter(pk__lte=40)",
      naive="Author.objects.filter(pk__lte=40)",
      notes="select_related works on the *reverse* side of a OneToOneField too, and a missing row "
            "costs no extra query - Django remembers that it is absent."),

    E(slug="sr-forward-o2o", level="medium", section=S, title="Forward one-to-one, then a FK",
      prompt="The first 25 AuthorProfile rows by pk.",
      consume=lambda qs: [(p.author.firstname, p.author.recommendedby and p.author.recommendedby.lastname) for p in qs],
      solution="AuthorProfile.objects.select_related('author__recommendedby').order_by('pk')[:25]",
      naive="AuthorProfile.objects.order_by('pk')[:25]",
      order_matters=True,
      notes="select_related follows a chain one JOIN per hop. The nullable hop becomes a LEFT "
             "JOIN, so authors without a recommender still come back - with None in place of the "
             "object."),

    E(slug="sr-nullable-chain", level="medium", section=S, title="Chain through a nullable FK",
      prompt="The first 60 books by pk. Most books have no series.",
      consume=lambda qs: [(b.title, b.series and b.series.name, b.series and b.series.publisher.lastname) for b in qs],
      solution="Book.objects.select_related('series__publisher').order_by('pk')[:60]",
      naive="Book.objects.order_by('pk')[:60]",
      order_matters=True,
      notes="Every nullable hop is another LEFT JOIN, never another query. Notice what the naive "
             "version costs: only books that have a series pay for it, so the query count follows "
             "the data rather than the row count."),

    E(slug="sr-only", level="hard", section=S, title="select_related + only()",
      prompt="The 50 books with the most pages, most pages first, ties broken by the lower id. Fetch no "
      "more columns than the grader needs (primary keys aside) and still pay a single query.",
      consume=lambda qs: [(b.title, b.genre, b.publisher.country) for b in qs],
      solution="Book.objects.select_related('publisher').only('title', 'genre', 'publisher__country')"
               ".order_by('-page_count', 'id')[:50]",
      naive="Book.objects.select_related('publisher').only('title', 'publisher__country')"
            ".order_by('-page_count', 'id')[:50]",
      order_matters=True,
      hints=["a starting point that is nearly right: "
             "Book.objects.order_by('-page_count', 'id').only('title')[:50]",
             "only() understands relation paths: only('title', 'publisher__country')."],
      notes="Touching a field you deferred triggers one extra SELECT *per row* - the same N+1 shape, "
            "from the opposite direction."),

    E(slug="sr-self-fk", level="medium", section=S, title="Self FK, two hops",
      prompt="Authors with pk <= 50, their recommender, and their recommender's recommender.",
      consume=lambda qs: [(a.firstname, a.recommendedby and a.recommendedby.firstname, a.recommendedby and a.recommendedby.recommendedby and a.recommendedby.recommendedby.firstname) for a in qs],
      solution="Author.objects.select_related('recommendedby__recommendedby').filter(pk__lte=50)",
      naive="Author.objects.filter(pk__lte=50)",
      notes="Django aliases the same table three times (T2, T3) - a self join costs nothing extra."),

    E(slug="sr-order-items", level="medium", section=S, title="Two branches at once",
      prompt="The first 40 OrderItems (by pk) that belong to an order with status 'paid'.",
      consume=lambda qs: [(i.book.title, i.order.user.username, i.quantity) for i in qs],
      solution="OrderItem.objects.filter(order__status='paid')"
               ".select_related('book', 'order__user').order_by('pk')[:40]",
      naive="OrderItem.objects.filter(order__status='paid').order_by('pk')[:40]",
      order_matters=True,
      notes="Two independent branches from one row are two JOINs in one query, and order__user "
             "is two hops along one path. Breadth and depth both stay free."),

    E(slug="sr-filter-is-not-select", level="medium", section=S, title="Filtering joins, but does not select",
      prompt="The first 40 books (by pk) whose publisher's country is 'JP' or 'DE'.",
      consume=lambda qs: [(b.title, b.publisher.country, b.publisher.lastname) for b in qs],
      solution="Book.objects.filter(publisher__country__in=['JP', 'DE'])"
               ".select_related('publisher').order_by('pk')[:40]",
      naive="Book.objects.filter(publisher__country__in=['JP', 'DE']).order_by('pk')[:40]",
      order_matters=True,
      notes="filter(publisher__country=...) already joins the publisher table, but it puts none of its "
            "columns in the SELECT list. Joining and selecting are separate decisions."),

    E(slug="sr-no-args", level="medium", section=S, title="select_related() with no arguments",
      prompt="The first 30 books by pk, without naming a single relation yourself.",
      consume=lambda qs: [(b.title, b.publisher.lastname) for b in qs],
      solution="Book.objects.select_related().order_by('pk')[:30]",
      naive="Book.objects.order_by('pk')[:30]",
      order_matters=True,
      notes="No-arg select_related() follows every non-nullable FK, recursively. Convenient in a shell, "
            "a liability in real code: add a FK later and every query silently grows a JOIN."),

    E(slug="sr-values-instead", level="easy", section=S, title="values() as the alternative",
      prompt="The 20 cheapest books that have a price (cheapest first, ties broken by the lower id) as a "
      "list of dicts with the keys 'title' and 'publisher__lastname'. No model instances.",
      solution="Book.objects.filter(price__isnull=False).order_by('price', 'id')"
               ".values('title', 'publisher__lastname')[:20]",
      order_matters=True,
      notes="values()/values_list() traverse FKs with a JOIN too. When you only need a couple of columns "
            "this beats select_related: no model instances are built at all."),

    E(slug="sr-fk-id-free", level="easy", section=S, title="The id you already have",
      prompt="(title, author_id) tuples for the first 100 books by pk - without joining the author table "
             "at all.",
      solution="Book.objects.order_by('pk').values_list('title', 'author_id')[:100]",
      order_matters=True,
      notes="b.author_id lives on the book row. Reaching for select_related('author') to read only the id "
            "buys you a pointless JOIN."),

    E(slug="sr-through-rows", level="easy", section=S, title="Both sides of a through model",
      prompt="The first 40 StoreStock rows by pk.",
      consume=lambda qs: [(x.store.name, x.book.title, x.quantity) for x in qs],
      solution="StoreStock.objects.select_related('store', 'book').order_by('pk')[:40]",
      naive="StoreStock.objects.order_by('pk')[:40]",
      order_matters=True,
      notes="A through row is an ordinary model with two forward FKs, so both sides come back in "
             "one JOIN each - which is why reaching for the through model is cheap once you need "
             "its own columns."),
]
