"""The 40 practice problems from the plainenglish.io article.

Field names match the article (firstname, lastname, joindate, popularity_score,
recommendedby, published_date).  A few prompts spell out the exact return shape
so the grader can compare your value with the reference answer.
"""

from ._base import Exercise as E

S = "basics"

EXERCISES = [
    E(slug="all-books", section=S, title="All books",
      prompt="Fetch every Book object from the database.",
      solution="Book.objects.all()"),

    E(slug="book-title-date", section=S, title="Two columns",
      prompt="Fetch the title and published_date of every book, as a list of (title, published_date) tuples.",
      solution="Book.objects.values_list('title', 'published_date')",
      hints=["values_list() returns tuples without building model instances."]),

    E(slug="new-authors", section=S, title="New authors",
      prompt="An author with popularity_score == 0 is 'new'. Return (firstname, lastname) tuples for all new authors.",
      solution="Author.objects.filter(popularity_score=0).values_list('firstname', 'lastname')"),

    E(slug="a-authors-score", section=S, title="Filter on two fields",
      prompt="Return (firstname, popularity_score) for authors whose firstname starts with 'A' "
             "and whose popularity_score is >= 8.",
      solution="Author.objects.filter(firstname__startswith='A', popularity_score__gte=8)"
               ".values_list('firstname', 'popularity_score')"),

    E(slug="aa-authors", section=S, title="Case-insensitive contains",
      prompt="Return a flat list of firstnames of every author with 'aa' in their firstname, case-insensitive.",
      solution="Author.objects.filter(firstname__icontains='aa').values_list('firstname', flat=True)",
      hints=["__icontains, plus flat=True on a single-field values_list."]),

    E(slug="authors-in-ids", section=S, title="__in lookup",
      prompt="Fetch the Author objects whose ids are in [1, 3, 23, 43, 134, 25].",
      solution="Author.objects.filter(pk__in=[1, 3, 23, 43, 134, 25])"),

    E(slug="pubs-since-sep-2012", section=S, title="Date filter + ordering",
      prompt="Publishers who joined on or after 2012-09-01: return (firstname, joindate) tuples "
             "ordered by joindate ascending.",
      solution="Publisher.objects.filter(joindate__gte=date(2012, 9, 1)).order_by('joindate')"
               ".values_list('firstname', 'joindate')",
      order_matters=True),

    E(slug="distinct-lastnames", section=S, title="distinct() + slice",
      prompt="Return the first 10 distinct publisher lastnames in alphabetical order, as a flat list.",
      solution="Publisher.objects.order_by('lastname').values_list('lastname', flat=True).distinct()[:10]",
      order_matters=True,
      hints=["distinct() looks at the selected columns only - so select just the one column."]),

    E(slug="last-signup-dates", section=S, title="Two aggregates, two tables",
      prompt="Return {'author': <latest Author joindate>, 'publisher': <latest Publisher joindate>}. "
             "Two tables means two queries - no more.",
      solution="{'author': Author.objects.aggregate(Max('joindate'))['joindate__max'],\n"
               " 'publisher': Publisher.objects.aggregate(Max('joindate'))['joindate__max']}"),

    E(slug="last-author-row", section=S, title="Latest row",
      prompt="Return the (firstname, lastname, joindate) tuple of the author who joined most recently.",
      solution="Author.objects.order_by('-joindate').values_list('firstname', 'lastname', 'joindate').first()",
      hints=["order_by('-joindate') then .first(), or .latest('joindate')."]),

    E(slug="authors-since-2013", section=S, title="Year lookup",
      prompt="Fetch the Author objects who joined in 2013 or later.",
      solution="Author.objects.filter(joindate__year__gte=2013)"),

    E(slug="sum-price-popular", section=S, title="Aggregate across a FK",
      prompt="Return the total price (a single number) of all books written by authors with "
             "popularity_score >= 7.",
      solution="Book.objects.filter(author__popularity_score__gte=7).aggregate(Sum('price'))['price__sum']"),

    E(slug="titles-of-a-authors", section=S, title="Flat list across a join",
      prompt="Return a flat list of the titles of all books whose author's firstname starts with 'A'. "
             "A list of titles, not a list of tuples.",
      solution="Book.objects.filter(author__firstname__startswith='A').values_list('title', flat=True)"),

    E(slug="sum-price-author-pks", section=S, title="Sum for a few authors",
      prompt="Return the total price of all books written by the authors with pk in [1, 3, 4].",
      solution="Book.objects.filter(author_id__in=[1, 3, 4]).aggregate(Sum('price'))['price__sum']"),

    E(slug="authors-and-recommender", section=S, title="Follow a FK in values_list",
      prompt="Return (firstname, recommender's firstname) tuples for every author - None where there is "
             "no recommender. One query only.",
      solution="Author.objects.values_list('firstname', 'recommendedby__firstname')",
      notes="Traversing a FK inside values_list()/values() is a JOIN, so it stays one query. "
            "select_related() is for when you want the *model instances*."),

    E(slug="authors-of-publisher-1", section=S, title="Reverse traversal + distinct",
      prompt="Authors who published a book with the publisher pk=1: return the Author objects ordered by "
             "firstname, without duplicates.",
      solution="Author.objects.filter(books__publisher_id=1).order_by('firstname').distinct()",
      order_matters=True,
      hints=["Joining to books multiplies rows - distinct() collapses them."]),

    E(slug="m2m-add-new-users", section=S, title="M2M: create and add", mutates=True,
      prompt="Create three new Users and add all three to the followers of author pk=1. "
             "Return the new follower count of author 1.",
      solution="a = Author.objects.get(pk=1)\n"
               "us = [User.objects.create(username=f'new{i}', email=f'new{i}@x.io') for i in range(3)]\n"
               "a.followers.add(*us)\n"
               "a.followers.count()",
      notes="add(*objs) is a single INSERT for all three rows; add() in a loop is one per row."),

    E(slug="m2m-set", section=S, title="M2M: set", mutates=True,
      prompt="Replace the followers of author pk=2 with exactly one user, the user pk=1. "
             "Return a flat list of the follower ids of author 2 afterwards.",
      solution="a = Author.objects.get(pk=2)\n"
               "a.followers.set([1])\n"
               "a.followers.values_list('id', flat=True)"),

    E(slug="m2m-add-existing", section=S, title="M2M: add existing", mutates=True,
      prompt="Add the users with pk 5, 6 and 7 to the followers of author pk=1. Return the new follower count.",
      solution="a = Author.objects.get(pk=1)\n"
               "a.followers.add(5, 6, 7)\n"
               "a.followers.count()",
      hints=["related managers accept pks directly, no need to fetch the User rows."]),

    E(slug="m2m-remove", section=S, title="M2M: remove", mutates=True,
      prompt="Remove author pk=1's lowest-pk follower from their followers. Return the new follower count.",
      solution="a = Author.objects.get(pk=1)\n"
               "a.followers.remove(a.followers.order_by('pk').first())\n"
               "a.followers.count()"),

    E(slug="reverse-m2m-user", section=S, title="Reverse M2M",
      prompt="Return a flat list of the firstnames of all authors that the user pk=1 follows - "
             "without touching the Author manager (no Author.objects).",
      solution="User.objects.get(pk=1).following.values_list('firstname', flat=True)",
      notes="The reverse side of Author.followers is User.following (related_name)."),

    E(slug="authors-title-tle", section=S, title="Reverse FK + icontains",
      prompt="Authors who wrote a book with 'tle' anywhere in the title (case-insensitive). "
             "Return distinct Author objects.",
      solution="Author.objects.filter(books__title__icontains='tle').distinct()"),

    E(slug="q-objects", section=S, title="Q objects",
      prompt="Authors whose firstname starts with 'a' (case-insensitive) AND who either have "
             "popularity_score > 5 or joined after 2014-12-31. Use Q objects.",
      solution="Author.objects.filter(Q(firstname__istartswith='a') & "
               "(Q(popularity_score__gt=5) | Q(joindate__gt=date(2014, 12, 31))))"),

    E(slug="get-author-1", section=S, title="get()",
      prompt="Retrieve the single Author object with pk=1.",
      solution="Author.objects.get(pk=1)"),

    E(slug="first-n-authors", section=S, title="Slicing",
      prompt="Retrieve the first 10 Author objects (by pk).",
      solution="Author.objects.order_by('pk')[:10]",
      order_matters=True),

    E(slug="first-last-score-7", section=S, title="first() and last()",
      prompt="Among authors with popularity_score == 7, return {'first': <lowest pk>, 'last': <highest pk>} "
             "as Author objects. Two queries.",
      solution="qs = Author.objects.filter(popularity_score=7).order_by('pk')\n"
               "{'first': qs.first(), 'last': qs.last()}"),

    E(slug="multi-filter-no-q", section=S, title="Four conditions, no Q",
      prompt="Authors who joined in 2012 or later, have popularity_score >= 4, joined on a day-of-month "
             "greater than 12, and whose firstname starts with 'a' (case-insensitive). No Q objects.",
      solution="Author.objects.filter(joindate__year__gte=2012, popularity_score__gte=4,\n"
               "                      joindate__day__gt=12, firstname__istartswith='a')"),

    E(slug="not-in-2012", section=S, title="exclude()",
      prompt="Fetch the Author objects who did NOT join in 2012.",
      solution="Author.objects.exclude(joindate__year=2012)"),

    E(slug="four-aggregates", section=S, title="Aggregate bundle",
      prompt="Return {'oldest': <min Author joindate>, 'newest': <max Author joindate>, "
             "'avg_score': <avg popularity_score>, 'total_price': <sum of all book prices>}. "
             "Two tables, so two queries - not four.",
      solution="a = Author.objects.aggregate(oldest=Min('joindate'), newest=Max('joindate'),\n"
               "                             avg_score=Avg('popularity_score'))\n"
               "{**a, 'total_price': Book.objects.aggregate(t=Sum('price'))['t']}",
      notes="Several aggregates over the same table cost one query - aggregate() takes as many as you like."),

    E(slug="no-recommender", section=S, title="isnull",
      prompt="Fetch the Author objects that have no recommender (recommendedby is null).",
      solution="Author.objects.filter(recommendedby__isnull=True)"),

    E(slug="null-author-books", section=S, title="Null across a join",
      prompt="Return {'no_author': <Book objects with no author>, 'orphan_recommender': "
             "<Book objects that have an author, but whose author has no recommender>}. Two queries.",
      solution="{'no_author': Book.objects.filter(author__isnull=True),\n"
               " 'orphan_recommender': Book.objects.filter(author__isnull=False, "
               "author__recommendedby__isnull=True)}"),

    E(slug="author-1-book-stats", section=S, title="Three aggregates, one query",
      prompt="For the books of author pk=1 return {'total_price': …, 'oldest': <min published_date>, "
             "'newest': <max published_date>}. This must cost exactly ONE query.",
      solution="Book.objects.filter(author_id=1).aggregate(total_price=Sum('price'),\n"
               "                                           oldest=Min('published_date'),\n"
               "                                           newest=Max('published_date'))",
      naive="{'total_price': Book.objects.filter(author_id=1).aggregate(s=Sum('price'))['s'],\n"
            " 'oldest': Book.objects.filter(author_id=1).aggregate(s=Min('published_date'))['s'],\n"
            " 'newest': Book.objects.filter(author_id=1).aggregate(s=Max('published_date'))['s']}"),

    E(slug="oldest-book", section=S, title="Min over a column",
      prompt="Return the earliest published_date of any book in the database.",
      solution="Book.objects.aggregate(Min('published_date'))['published_date__min']"),

    E(slug="avg-price", section=S, title="Average",
      prompt="Return the average price of all books in the database.",
      solution="Book.objects.aggregate(Avg('price'))['price__avg']"),

    E(slug="max-publisher-score", section=S, title="Reverse FK hop",
      prompt="Return the highest popularity_score among the publishers that published a book "
             "for the author pk=1. One query.",
      solution="Publisher.objects.filter(books__author_id=1).aggregate(Max('popularity_score'))"
               "['popularity_score__max']"),

    E(slug="count-authors-ab", section=S, title="count() across a join",
      prompt="How many distinct authors wrote a book whose title contains 'ab' (case-insensitive)? "
             "Return the number.",
      solution="Author.objects.filter(books__title__icontains='ab').distinct().count()"),

    E(slug="followers-gt-216", section=S, title="Annotate then filter",
      prompt="Fetch the Author objects with more than 216 followers.",
      solution="Author.objects.annotate(n=Count('followers')).filter(n__gt=216)",
      hints=["Count() over the M2M, then filter on the annotation."]),

    E(slug="avg-score-late-joiners", section=S, title="Average with a filter",
      prompt="Return the average popularity_score of all authors who joined after 2014-09-20.",
      solution="Author.objects.filter(joindate__gt=date(2014, 9, 20))"
               ".aggregate(Avg('popularity_score'))['popularity_score__avg']"),

    E(slug="books-of-prolific-authors", section=S, title="Subquery in a filter",
      prompt="Fetch the Book objects whose author has written more than 10 books. One query.",
      solution="Book.objects.filter(author__in=Author.objects.annotate(n=Count('books')).filter(n__gt=10))",
      notes="Passing a queryset to __in becomes a subquery, so it stays one round-trip."),

    E(slug="duplicate-titles", section=S, title="Group by having",
      prompt="Return a flat list of the titles that are shared by more than one book.",
      solution="Book.objects.values('title').annotate(n=Count('id')).filter(n__gt=1)"
               ".values_list('title', flat=True)",
      hints=["values() before annotate() is how you say GROUP BY."]),
]
