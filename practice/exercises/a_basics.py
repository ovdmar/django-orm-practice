"""The 40 practice problems from the plainenglish.io article.

Field names match the article (firstname, lastname, joindate, popularity_score,
recommendedby, published_date).  A few prompts spell out the exact return shape
so the grader can compare your value with the reference answer.
"""

from ._base import Exercise as E

S = "basics"

EXERCISES = [
    E(slug="all-books", level="easy", section=S, title="All books",
      prompt="Fetch every Book object from the database.",
      solution="Book.objects.all()",
      notes="all() is not a query yet. Nothing runs until the queryset is iterated, sliced with "
             "a step or turned into a list - which is exactly what lets you add select_related() "
             "to it later.",
      alternatives=(
          ("bad",
           "Book.objects.values()",
           "values() hands back dicts, not the model objects asked for"),
      )),

    E(slug="book-title-date", level="easy", section=S, title="Two columns",
      prompt="Fetch the title and published_date of every book, as a list of (title, published_date) tuples.",
      solution="Book.objects.values_list('title', 'published_date')",
      hints=["values_list() returns tuples without building model instances."],
      notes="values_list() builds no model instances, so it is lighter in both queries and "
             "memory. The cost is tuples: no methods, no related objects, no laziness left to "
             "exploit.",
      alternatives=(
          ("good",
           "Book.objects.values_list('title', 'published_date', named=True)",
           "named=True gives row.title instead of row[0], for the same single query"),
          ("bad",
           "Book.objects.values('title', 'published_date')",
           "dicts, where tuples were asked for"),
      )),

    E(slug="new-authors", level="easy", section=S, title="New authors",
      prompt="An author with popularity_score == 0 is 'new'. Return (firstname, lastname) tuples for all new authors.",
      solution="Author.objects.filter(popularity_score=0).values_list('firstname', 'lastname')",
      notes="An = filter is an exact SQL comparison and nothing more. popularity_score=0 finds "
             "zeros, never NULLs - those need __isnull.",
      alternatives=(
          ("bad",
           "Author.objects.filter(popularity_score__isnull=True).values_list('firstname', 'lastname')",
           "0 and NULL are different things, and no score here is NULL - this finds nothing"),
      )),

    E(slug="a-authors-score", level="easy", section=S, title="Filter on two fields",
      prompt="Return (firstname, popularity_score) for authors whose firstname starts with 'A' "
             "and whose popularity_score is >= 8.",
      solution="Author.objects.filter(firstname__startswith='A', popularity_score__gte=8)"
               ".values_list('firstname', 'popularity_score')",
      notes="Keyword arguments to filter() are ANDed into one WHERE clause, so the number of "
             "conditions never changes the number of queries.",
      alternatives=(
          ("bad",
           "Author.objects.filter(firstname__startswith='A', popularity_score__gt=8).values_list('firstname', 'popularity_score')",
           "__gt=8 drops the authors who score exactly 8"),
      )),

    E(slug="aa-authors", level="easy", section=S, title="Case-insensitive contains",
      prompt="Return a flat list of firstnames of every author with 'aa' in their firstname, case-insensitive.",
      solution="Author.objects.filter(firstname__icontains='aa').values_list('firstname', flat=True)",
      hints=["__icontains, plus flat=True on a single-field values_list."],
      notes="__icontains becomes LIKE '%aa%'. A leading wildcard cannot use an index, so this is "
             "a full scan - harmless here, a warning sign on a big table. And mind the backend: "
             "SQLite's LIKE ignores ASCII case, so plain contains and startswith behave like the "
             "i-variants here but would not on PostgreSQL.",
      alternatives=(
          ("bad",
           "Author.objects.filter(firstname__istartswith='aa').values_list('firstname', flat=True)",
           "istartswith anchors at the beginning, so Haakon, Isaac and Maarten are missed"),
      )),

    E(slug="authors-in-ids", level="easy", section=S, title="__in lookup",
      prompt="Fetch the Author objects whose ids are in [1, 3, 23, 43, 134, 25].",
      solution="Author.objects.filter(pk__in=[1, 3, 23, 43, 134, 25])",
      notes="pk is an alias for whichever field is the primary key, so pk__in works without "
             "knowing that the column happens to be called id.",
      alternatives=(
          ("bad",
           "[Author.objects.get(pk=i) for i in [1, 3, 23, 43, 134, 25]]",
           "a query per id, and it raises DoesNotExist instead of skipping one that is missing"),
          ("bad",
           "Author.objects.filter(pk=[1, 3, 23, 43, 134, 25])",
           "a list where a single value is expected - pk=... takes one, pk__in=... takes many"),
      )),

    E(slug="pubs-since-sep-2012", level="easy", section=S, title="Date filter + ordering",
      prompt="Publishers who joined on or after 2012-09-01: return (firstname, joindate) tuples "
             "ordered by joindate ascending.",
      solution="Publisher.objects.filter(joindate__gte=date(2012, 9, 1)).order_by('joindate')"
               ".values_list('firstname', 'joindate')",
      order_matters=True,
      notes="A date object compares straight against a DateField. Meta.ordering supplies a "
             "default order, but saying the order you need is what makes a result reproducible "
             "once slices and joins are involved.",
      alternatives=(
          ("bad",
           "Publisher.objects.filter(joindate__year__gte=2012).order_by('joindate').values_list('firstname', 'joindate')",
           "the whole of 2012, not from September onwards"),
      )),

    E(slug="distinct-lastnames", level="medium", section=S, title="distinct() + slice",
      prompt="Return the first 10 publisher lastnames in alphabetical order, with no repeats, "
             "as a flat list.",
      solution="Publisher.objects.order_by('lastname').values_list('lastname', flat=True).distinct()[:10]",
      order_matters=True,
      hints=["distinct() looks at the selected columns only - so select just the one column."],
      notes="DISTINCT applies to the whole selected row, so it only collapses duplicates when "
             "you select just the column you care about. The slice afterwards is a LIMIT on the "
             "same query.",
      alternatives=(
          ("careful",
           "sorted(set(Publisher.objects.values_list('lastname', flat=True)))[:10]",
           "one query too, but it ships every row to de-duplicate in Python"),
          ("bad",
           "Publisher.objects.order_by('lastname').values_list('id', 'lastname').distinct()[:10]",
           "DISTINCT covers every selected column, so adding id makes each row unique again"),
      )),

    E(slug="last-signup-dates", level="medium", section=S, title="Two aggregates, two tables",
      prompt="Return {'author': <latest Author joindate>, 'publisher': <latest Publisher joindate>}.",
      solution="{'author': Author.objects.aggregate(Max('joindate'))['joindate__max'],\n"
               " 'publisher': Publisher.objects.aggregate(Max('joindate'))['joindate__max']}",
      notes="aggregate() ends the queryset and returns a plain dict - there is nothing left to "
             "chain. Two tables cannot share one aggregate, which is why this costs two round "
             "trips and not one.",
      alternatives=(
          ("good",
           "{'author': Author.objects.latest('joindate').joindate,\n"
           " 'publisher': Publisher.objects.latest('joindate').joindate}",
           "latest() fetches the whole row to read one date out of it - same two queries"),
          ("bad",
           "{'author': Author.objects.first().joindate,\n"
           " 'publisher': Publisher.objects.first().joindate}",
           "first() is the lowest pk, not the latest date"),
      )),

    E(slug="last-author-row", level="easy", section=S, title="Latest row",
      prompt="Return the (firstname, lastname, joindate) tuple of the author who joined most recently.",
      solution="Author.objects.order_by('-joindate').values_list('firstname', 'lastname', 'joindate').first()",
      hints=["order_by('-joindate') then .first(), or .latest('joindate')."],
      notes="first() adds LIMIT 1 and returns None on an empty queryset; latest() does the same "
             "but insists on a field to order by. Neither reads the rest of the table.",
      alternatives=(
          ("good",
           "Author.objects.values_list('firstname', 'lastname', 'joindate').latest('joindate')",
           "latest() states the intent and refuses to run without a field to order by"),
          ("bad",
           "Author.objects.values_list('firstname', 'lastname', 'joindate').last()",
           "last() takes the highest pk - Meta.ordering here is by pk, not by joindate"),
      )),

    E(slug="authors-since-2013", level="easy", section=S, title="Year lookup",
      prompt="Fetch the Author objects who joined in 2013 or later.",
      solution="Author.objects.filter(joindate__year__gte=2013)",
      notes="Django rewrites __year into a plain date comparison (joindate >= 2013-01-01), so an "
             "index on the column is still usable - unlike wrapping the column in a function "
             "yourself.",
      alternatives=(
          ("bad",
           "Author.objects.filter(joindate__year=2013)",
           "only 2013, not 2013 and later"),
      )),

    E(slug="sum-price-popular", level="easy", section=S, title="Aggregate across a FK",
      prompt="Return the total price (a single number) of all books written by authors with "
             "popularity_score >= 7.",
      solution="Book.objects.filter(author__popularity_score__gte=7).aggregate(Sum('price'))['price__sum']",
      notes="The aggregate runs over the join, so the database sums exactly the rows that "
             "matched. Summing in Python would have pulled every book across the wire first.",
      alternatives=(
          ("bad",
           "sum(b.price for b in Book.objects.filter(author__popularity_score__gte=7))",
           "an unpriced book makes this raise; SQL's SUM skips NULLs"),
      )),

    E(slug="titles-of-a-authors", level="easy", section=S, title="Flat list across a join",
      prompt="Return a flat list of the titles of all books whose author's firstname starts with 'A'. "
             "A list of titles, not a list of tuples.",
      solution="Book.objects.filter(author__firstname__startswith='A').values_list('title', flat=True)",
      notes="flat=True unwraps the single-column tuples. Without it you get [(title,), ...], a "
             "shape mistake that usually surfaces somewhere far away.",
      alternatives=(
          ("bad",
           "Book.objects.filter(author__firstname__startswith='A').values_list('title')",
           "without flat=True every title arrives wrapped in a one-element tuple"),
      )),

    E(slug="sum-price-author-pks", level="easy", section=S, title="Sum for a few authors",
      prompt="Return the total price of all books written by the authors with pk in [1, 3, 4].",
      solution="Book.objects.filter(author_id__in=[1, 3, 4]).aggregate(Sum('price'))['price__sum']",
      notes="Filtering on author_id touches no second table: the value is already on the book "
             "row, so there is no join to pay for.",
      alternatives=(
          ("bad",
           "sum(Book.objects.filter(author_id=pk).aggregate(s=Sum('price'))['s'] for pk in [1, 3, 4])",
           "a query per author for a sum one WHERE ... IN can do"),
      )),

    E(slug="authors-and-recommender", level="medium", section=S, title="Follow a FK in values_list",
      prompt="Return (firstname, recommender's firstname) tuples for every author - None where there is "
      "no recommender.",
      solution="Author.objects.values_list('firstname', 'recommendedby__firstname')",
      notes="Traversing a FK inside values_list()/values() is a JOIN, so it stays one query. "
            "select_related() is for when you want the *model instances*.",
      alternatives=(
          ("bad",
           "[(a.firstname, a.recommendedby.firstname if a.recommendedby else None)\n"
           " for a in Author.objects.all()]",
           "a query per author to read a name the JOIN already has"),
      )),

    E(slug="authors-of-publisher-1", level="medium", section=S, title="Reverse traversal + distinct",
      prompt="Authors who published a book with the publisher pk=1: return the Author objects ordered by "
             "firstname, without duplicates.",
      solution="Author.objects.filter(books__publisher_id=1).order_by('firstname').distinct()",
      order_matters=True,
      hints=["Joining to books multiplies rows - distinct() collapses them."],
      notes="Following a reverse relation in filter() joins, and the join can return an author "
             "once per matching book. distinct() is what turns the result back into a set of "
             "authors.",
      alternatives=(
          ("bad",
           "Author.objects.filter(books__publisher_id=1).order_by('firstname')",
           "no distinct(), so an author who published several books there comes back several times"),
      )),

    E(slug="m2m-add-new-users", level="medium", section=S, title="M2M: create and add", mutates=True,
      prompt="Create three new Users and add all three to the followers of author pk=1. "
             "Return the new follower count of author 1.",
      solution="a = Author.objects.get(pk=1)\n"
               "us = [User.objects.create(username=f'new{i}', email=f'new{i}@x.io') for i in range(3)]\n"
               "a.followers.add(*us)\n"
               "a.followers.count()",
      notes="add(*objs) is a single INSERT for all three rows; add() in a loop is one per row.",
      alternatives=(
          ("bad",
           "a = Author.objects.get(pk=1)\n"
           "for i in range(3):\n"
           "    a.followers.add(User.objects.create(username=f'new{i}', email='new@x.io'))\n"
           "a.followers.count()",
           "add() per user is an INSERT each; add(*users) is one"),
      )),

    E(slug="m2m-set", level="easy", section=S, title="M2M: set", mutates=True,
      prompt="Replace the followers of author pk=2 with exactly one user, the user pk=1. "
             "Return a flat list of the follower ids of author 2 afterwards.",
      solution="a = Author.objects.get(pk=2)\n"
               "a.followers.set([1])\n"
               "a.followers.values_list('id', flat=True)",
      notes="set() works out the difference and issues only the inserts and deletes needed, so "
             "rows that should stay are left alone rather than cleared and re-added.",
      alternatives=(
          ("bad",
           "a = Author.objects.get(pk=2)\n"
           "a.followers.add(1)\n"
           "a.followers.values_list('id', flat=True)",
           "add() only adds - the followers author 2 already had are still there"),
      )),

    E(slug="m2m-add-existing", level="easy", section=S, title="M2M: add existing", mutates=True,
      prompt="Add the users with pk 5, 6 and 7 to the followers of author pk=1. Return the new follower count.",
      solution="a = Author.objects.get(pk=1)\n"
               "a.followers.add(5, 6, 7)\n"
               "a.followers.count()",
      hints=["related managers accept pks directly, no need to fetch the User rows."],
      notes="Related managers accept primary keys as well as instances, so adding a known id "
             "costs no SELECT first.",
      alternatives=(
          ("bad",
           "a = Author.objects.get(pk=1)\n"
           "for pk in (5, 6, 7):\n"
           "    a.followers.add(pk)\n"
           "a.followers.count()",
           "three INSERTs where add(5, 6, 7) is one"),
      )),

    E(slug="m2m-remove", level="medium", section=S, title="M2M: remove", mutates=True,
      prompt="Remove author pk=1's lowest-pk follower from their followers. Return the new follower count.",
      solution="a = Author.objects.get(pk=1)\n"
               "a.followers.remove(a.followers.order_by('pk').first())\n"
               "a.followers.count()",
      notes="remove() deletes rows from the through table only - the User rows are untouched. "
             "clear() would drop every link, and delete() on the manager is not the same thing at "
             "all.",
      alternatives=(
          ("bad",
           "a = Author.objects.get(pk=1)\n"
           "a.followers.clear()\n"
           "a.followers.count()",
           "clear() drops every follower, not the one you meant"),
      )),

    E(slug="reverse-m2m-user", level="medium", section=S, title="Reverse M2M",
      prompt="Return a flat list of the firstnames of all authors that the user pk=1 follows - "
             "without touching the Author manager (no Author.objects).",
      solution="User.objects.get(pk=1).following.values_list('firstname', flat=True)",
      notes="The reverse side of Author.followers is User.following (related_name).",
      alternatives=(
          ("bad",
           "User.objects.get(pk=1).following.all()",
           "Author objects, where firstnames were asked for"),
      )),

    E(slug="authors-title-tle", level="easy", section=S, title="Reverse FK + icontains",
      prompt="Authors who wrote a book with 'tle' anywhere in the title (case-insensitive). "
             "Return Author objects, each one once.",
      solution="Author.objects.filter(books__title__icontains='tle').distinct()",
      notes="The same shape as the publisher exercise: a join through a reverse FK multiplies "
             "rows, and distinct() collapses them again.",
      alternatives=(
          ("bad",
           "Author.objects.filter(books__title__icontains='tle')",
           "no distinct(), so an author with two matching books appears twice"),
      )),

    E(slug="q-objects", level="medium", section=S, title="Q objects",
      prompt="Authors whose firstname starts with 'a' (case-insensitive) who additionally either "
             "have popularity_score > 5 or joined after 2014-12-31.",
      hints=["filter(**kwargs) can only AND its conditions together."],
      solution="Author.objects.filter(Q(firstname__istartswith='a') & "
               "(Q(popularity_score__gt=5) | Q(joindate__gt=date(2014, 12, 31))))",
      notes="filter(**kwargs) can only AND. Q objects add OR, negation (~Q) and parentheses - "
             "and all of it still compiles into one WHERE clause.",
      alternatives=(
          ("good",
           "Author.objects.filter(firstname__istartswith='a').filter(\n"
           "    Q(popularity_score__gt=5) | Q(joindate__gt=date(2014, 12, 31)))",
           "chaining the AND part keeps Q objects for the OR alone, which reads better"),
          ("bad",
           "Author.objects.filter(Q(firstname__istartswith='a') | Q(popularity_score__gt=5)\n"
           "                      | Q(joindate__gt=date(2014, 12, 31)))",
           "ORed throughout, so the firstname requirement stops being a requirement"),
      )),

    E(slug="get-author-1", level="easy", section=S, title="get()",
      prompt="Retrieve the single Author object with pk=1.",
      solution="Author.objects.get(pk=1)",
      notes="get() raises DoesNotExist when there is no row and MultipleObjectsReturned when "
             "there is more than one. That strictness is the whole point of it; filter().first() "
             "is the forgiving version.",
      alternatives=(
          ("bad",
           "Author.objects.filter(pk=1)",
           "a queryset holding one author, not the author"),
      )),

    E(slug="first-n-authors", level="easy", section=S, title="Slicing",
      prompt="Retrieve the first 10 Author objects (by pk).",
      solution="Author.objects.order_by('pk')[:10]",
      order_matters=True,
      notes="Slicing a queryset becomes LIMIT, so only ten rows cross the wire. A slice with a "
             "step - or a negative index - cannot be expressed in SQL and evaluates the queryset "
             "instead.",
      alternatives=(
          ("bad",
           "[Author.objects.get(pk=i) for i in range(1, 11)]",
           "ten queries for what LIMIT 10 does in one, and it assumes ids 1..10 all exist"),
      )),

    E(slug="first-last-score-7", level="medium", section=S, title="first() and last()",
      prompt="Among authors with popularity_score == 7, return {'first': <lowest pk>, 'last': <highest "
      "pk>} as Author objects.",
      solution="qs = Author.objects.filter(popularity_score=7).order_by('pk')\n"
               "{'first': qs.first(), 'last': qs.last()}",
      notes="first() and last() are a LIMIT 1 each, last() simply reversing the ordering. "
             "Reusing the queryset variable does not reuse the result: each one is its own query.",
      alternatives=(
          ("careful",
           "qs = Author.objects.filter(popularity_score=7).order_by('pk')\n"
           "{'first': qs[0], 'last': qs[len(qs) - 1]}",
           "one query rather than two: len() evaluates the queryset and the slices read its cache - at the price of holding every matching row in memory"),
          ("bad",
           "qs = Author.objects.filter(popularity_score=7)\n"
           "{'first': qs.earliest('joindate'), 'last': qs.latest('joindate')}",
           "earliest and latest order by the date, so this is a different pair of authors"),
      )),

    E(slug="multi-filter-no-q", level="medium", section=S, title="Four conditions, no Q",
      prompt="Authors who joined in 2012 or later, have popularity_score >= 4, joined on a day-of-month "
      "greater than 12, and whose firstname starts with 'a' (case-insensitive).",
      solution="Author.objects.filter(joindate__year__gte=2012, popularity_score__gte=4,\n"
               "                      joindate__day__gt=12, firstname__istartswith='a')",
      notes="Conditions inside one filter() call all apply to the same row. Chaining "
             ".filter().filter() means the same thing for a plain field, but not across a multi- "
             "valued relation, where each call can match a different related row.",
      alternatives=(
          ("bad",
           "Author.objects.filter(joindate__year__gte=2012, popularity_score__gte=4,\n"
           "                      joindate__day__gte=12, firstname__istartswith='a')",
           "day__gte includes the 12th, and the task asks for later than the 12th"),
      )),

    E(slug="not-in-2012", level="easy", section=S, title="exclude()",
      prompt="Fetch the Author objects who did NOT join in 2012.",
      solution="Author.objects.exclude(joindate__year=2012)",
      notes="exclude() negates the whole condition, which matters as soon as there is more than "
             "one: exclude(a=1, b=2) drops rows matching both, not rows matching either.",
      alternatives=(
          ("bad",
           "Author.objects.filter(joindate__year__ne=2012)",
           "there is no __ne lookup - exclude() is how the ORM negates"),
      )),

    E(slug="four-aggregates", level="medium", section=S, title="Aggregate bundle",
      prompt="Return {'oldest': <min Author joindate>, 'newest': <max Author joindate>, 'avg_score': "
      "<avg popularity_score>, 'total_price': <sum of all book prices>}.",
      solution="a = Author.objects.aggregate(oldest=Min('joindate'), newest=Max('joindate'),\n"
               "                             avg_score=Avg('popularity_score'))\n"
               "{**a, 'total_price': Book.objects.aggregate(t=Sum('price'))['t']}",
      notes="Several aggregates over the same table cost one query - aggregate() takes as many as you like.",
      alternatives=(
          ("bad",
           "{'oldest': Author.objects.aggregate(v=Min('joindate'))['v'],\n"
           " 'newest': Author.objects.aggregate(v=Max('joindate'))['v'],\n"
           " 'avg_score': Author.objects.aggregate(v=Avg('popularity_score'))['v'],\n"
           " 'total_price': Book.objects.aggregate(v=Sum('price'))['v']}",
           "four scans of two tables for what two queries compute"),
      )),

    E(slug="no-recommender", level="easy", section=S, title="isnull",
      prompt="Fetch the Author objects that have no recommender (recommendedby is null).",
      solution="Author.objects.filter(recommendedby__isnull=True)",
      notes="__isnull=True is how you ask for NULL. Comparing to None with = would not become "
             "SQL's IS NULL.",
      alternatives=(
          ("bad",
           "Author.objects.filter(recommended__isnull=True)",
           "recommended is the reverse side - the authors nobody was recommended by"),
      )),

    E(slug="null-author-books", level="medium", section=S, title="Null across a join",
      prompt="Return {'no_author': <Book objects with no author>, 'orphan_recommender': <Book objects "
      "that have an author, but whose author has no recommender>}.",
      solution="{'no_author': Book.objects.filter(author__isnull=True),\n"
               " 'orphan_recommender': Book.objects.filter(author__isnull=False, "
               "author__recommendedby__isnull=True)}",
      notes="A nullable FK poses two different questions - the row has no author, or the author "
             "exists but its own FK is null - and they need different joins, so they cannot share "
             "a query.",
      alternatives=(
          ("bad",
           "{'no_author': Book.objects.filter(author=None),\n"
           " 'orphan_recommender': Book.objects.filter(author__recommendedby__isnull=True)}",
           "without author__isnull=False the second set swallows the authorless books too"),
      )),

    E(slug="author-1-book-stats", level="medium", section=S, title="Three aggregates, one query",
      prompt="For the books of author pk=1 return {'total_price': …, 'oldest': <min published_date>, "
      "'newest': <max published_date>}.",
      solution="Book.objects.filter(author_id=1).aggregate(total_price=Sum('price'),\n"
               "                                           oldest=Min('published_date'),\n"
               "                                           newest=Max('published_date'))",
      naive="{'total_price': Book.objects.filter(author_id=1).aggregate(s=Sum('price'))['s'],\n"
            " 'oldest': Book.objects.filter(author_id=1).aggregate(s=Min('published_date'))['s'],\n"
            " 'newest': Book.objects.filter(author_id=1).aggregate(s=Max('published_date'))['s']}",
      notes="aggregate() takes as many aggregates as you like and computes them in one pass over "
             "the matched rows. Three separate calls would scan the same rows three times.",
      alternatives=(
          ("bad",
           "{'total_price': Book.objects.filter(author_id=1).aggregate(v=Sum('price'))['v'],\n"
           " 'oldest': Book.objects.filter(author_id=1).aggregate(v=Min('published_date'))['v'],\n"
           " 'newest': Book.objects.filter(author_id=1).aggregate(v=Max('published_date'))['v']}",
           "three scans of the same rows for three numbers one scan can produce"),
      )),

    E(slug="oldest-book", level="easy", section=S, title="Min over a column",
      prompt="Return the earliest published_date of any book in the database.",
      solution="Book.objects.aggregate(Min('published_date'))['published_date__min']",
      notes="The database finds the minimum without shipping a single date to Python. With an "
             "index on the column it does not even scan.",
      alternatives=(
          ("good",
           "Book.objects.order_by('published_date').first().published_date",
           "ORDER BY plus LIMIT 1 instead of MIN - one query either way"),
          ("bad",
           "Book.objects.aggregate(Min('published_date'))",
           "the dict aggregate() returns, not the date inside it"),
      )),

    E(slug="avg-price", level="easy", section=S, title="Average",
      prompt="Return the average price of all books in the database.",
      solution="Book.objects.aggregate(Avg('price'))['price__avg']",
      notes="AVG ignores NULLs, so unpriced books leave both the sum and the count alone. That "
             "is usually what you want - but it is SQL deciding, not you.",
      alternatives=(
          ("bad",
           "sum(b.price for b in Book.objects.all()) / Book.objects.count()",
           "NULL prices make it raise, and it would divide by every book rather than the priced ones"),
      )),

    E(slug="max-publisher-score", level="medium", section=S, title="Reverse FK hop",
      prompt="Return the highest popularity_score among the publishers that published a book for the "
      "author pk=1.",
      solution="Publisher.objects.filter(books__author_id=1).aggregate(Max('popularity_score'))"
               "['popularity_score__max']",
      notes="Aggregating over a reverse relation joins to it first. MAX is indifferent to the "
             "duplicate rows a join produces; SUM and COUNT are not.",
      alternatives=(
          ("good",
           "Publisher.objects.filter(books__author_id=1).order_by(\n"
           "    '-popularity_score').first().popularity_score",
           "ORDER BY plus LIMIT 1 instead of MAX - one query either way"),
          ("bad",
           "Book.objects.filter(author_id=1).aggregate(Max('popularity_score'))['popularity_score__max']",
           "popularity_score lives on the publisher; from Book it has to be traversed as publisher__popularity_score"),
      )),

    E(slug="count-authors-ab", level="medium", section=S, title="count() across a join",
      prompt="How many different authors wrote a book whose title contains 'ab' "
             "(case-insensitive)? Return the number.",
      solution="Author.objects.filter(books__title__icontains='ab').distinct().count()",
      notes="count() asks the database for the number. len(queryset) would fetch every row and "
             "count them in Python - the same answer at a very different price.",
      alternatives=(
          ("good",
           "Author.objects.filter(Exists(\n"
           "    Book.objects.filter(author=OuterRef('pk'), title__icontains='ab'))).count()",
           "Exists() needs no DISTINCT because it never multiplies the rows"),
          ("bad",
           "Author.objects.filter(books__title__icontains='ab').count()",
           "counts one row per matching book, so prolific authors are counted twice and more"),
      )),

    E(slug="followers-gt-216", level="medium", section=S, title="Annotate then filter",
      prompt="Fetch the Author objects with more than 216 followers.",
      solution="Author.objects.annotate(n=Count('followers')).filter(n__gt=216)",
      hints=["Count() over the M2M, then filter on the annotation."],
      notes="An annotation is a column on the query, so filtering on it becomes HAVING after a "
             "GROUP BY. Django decides which of WHERE and HAVING your condition belongs in.",
      alternatives=(
          ("bad",
           "[a for a in Author.objects.all() if a.followers.count() > 216]",
           "a COUNT query per author - 151 of them"),
      )),

    E(slug="avg-score-late-joiners", level="easy", section=S, title="Average with a filter",
      prompt="Return the average popularity_score of all authors who joined after 2014-09-20.",
      solution="Author.objects.filter(joindate__gt=date(2014, 9, 20))"
               ".aggregate(Avg('popularity_score'))['popularity_score__avg']",
      notes="WHERE runs before the aggregate, so the average covers the matching rows only. "
             "Filtering after an aggregate is a different question, and becomes HAVING.",
      alternatives=(
          ("bad",
           "Author.objects.aggregate(Avg('popularity_score'))['popularity_score__avg']",
           "every author, with the joindate filter forgotten"),
      )),

    E(slug="books-of-prolific-authors", level="hard", section=S, title="Subquery in a filter",
      prompt="Fetch the Book objects whose author has written more than 10 books.",
      solution="Book.objects.filter(author__in=Author.objects.annotate(n=Count('books')).filter(n__gt=10))",
      notes="Passing a queryset to __in becomes a subquery, so it stays one round-trip.",
      alternatives=(
          ("good",
           "Book.objects.annotate(n=Count('author__books')).filter(n__gt=10)",
           "counting the author's books from the book row itself - one query, no subquery"),
          ("bad",
           "Book.objects.filter(author__books__count__gt=10)",
           "there is no __count lookup on a relation; annotate first, or pass a queryset to __in"),
      )),

    E(slug="duplicate-titles", level="hard", section=S, title="Group by having",
      prompt="Return a flat list of the titles that are shared by more than one book.",
      solution="Book.objects.values('title').annotate(n=Count('id')).filter(n__gt=1)"
               ".values_list('title', flat=True)",
      hints=["values() before annotate() is how you say GROUP BY."],
      notes="values() before annotate() sets the GROUP BY; filtering after annotate() becomes "
             "HAVING. Swap the order and you have asked something else entirely.",
      alternatives=(
          ("bad",
           "[t for t in set(Book.objects.values_list('title', flat=True))\n"
           " if Book.objects.filter(title=t).count() > 1]",
           "a COUNT query per distinct title - hundreds of them, for one GROUP BY"),
      )),
]
