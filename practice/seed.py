"""Deterministic fixture data. Same RNG seed -> same database every run."""

import random
from datetime import date, timedelta

FIRST = [
    "Aaron", "Aaliyah", "Aada", "Abigail", "Adam", "Alice", "Amir", "Andrei", "Anna",
    "Bella", "Ben", "Carla", "Chen", "Daniel", "Diana", "Elena", "Emil", "Farah",
    "Gabriel", "Haakon", "Hana", "Ines", "Isaac", "Jonas", "Julia", "Karim", "Klara",
    "Lars", "Lena", "Maarten", "Maria", "Nadia", "Nils", "Olga", "Omar", "Petra",
    "Pavel", "Quinn", "Rania", "Rosa", "Sam", "Sofia", "Tomas", "Tara", "Umar",
    "Vera", "Viktor", "Wanda", "Yara", "Zane", "Zoe",
]
LAST = [
    "Alvarez", "Novak", "Ionescu", "Kowalski", "Fischer", "Moreau", "Bianchi",
    "Svensson", "Nakamura", "Okafor", "Costa", "Dimitrov",
]
STREETS = ["Oak St", "Main Rd", "Park Ave", "Elm St", "Cedar Ln", "Hill Rd"]
ADJ = [
    "Little", "Subtle", "Absent", "Hidden", "Broken", "Golden", "Silent", "Last",
    "Abandoned", "Crimson", "Northern", "Quiet", "Wild", "Second", "Fabled",
    "Gentle", "Hollow", "Distant", "Bitter", "Endless",
]
NOUN = [
    "Battle", "Castle", "Fable", "Cabin", "Abyss", "Garden", "Machine", "River",
    "Kingdom", "Letter", "Mirror", "Harvest", "Lantern", "Orchard", "Compass",
    "Tablet", "Cabaret", "Meridian",
]
GENRES = ["fiction", "fantasy", "sci-fi", "mystery", "romance", "history", "poetry", "horror"]
COUNTRIES = ["US", "UK", "DE", "FR", "JP", "RO"]
CITIES = ["Berlin", "Lisbon", "Osaka", "Cluj", "Lyon", "Leeds", "Austin", "Turin"]
TAGS = [
    "bestseller", "award-winner", "translated", "signed", "debut", "banned",
    "book-club", "illustrated", "sequel", "classic", "staff-pick", "reprint",
    "audiobook", "limited",
]
REVIEW_TEXT = [
    "Could not put it down.", "Dragged in the middle.", "A quiet masterpiece.",
    "Overrated but fun.", "Beautiful prose, thin plot.", "Read it twice.",
    "Not for me.", "Best of the year.", "Solid, unremarkable.", "Wildly inventive.",
]


def _d(rng, start, end):
    return start + timedelta(days=rng.randrange((end - start).days + 1))


def seed(verbose=False):
    from bookstore.models import (
        Author, AuthorProfile, Book, Order, OrderItem, Publisher, Review, Series,
        Store, StoreStock, Tag, TaggedItem, User,
    )
    from django.contrib.contenttypes.models import ContentType

    rng = random.Random(20240917)

    # --- users -------------------------------------------------------------
    users = [
        User(username=f"{FIRST[i % len(FIRST)].lower()}{i}", email=f"user{i}@example.com")
        for i in range(260)
    ]
    User.objects.bulk_create(users)
    users = list(User.objects.all())

    # --- authors -----------------------------------------------------------
    authors = []
    for i in range(150):
        # ~1 in 9 authors is "new" (popularity_score == 0)
        score = 0 if i % 9 == 3 else rng.randrange(1, 11)
        authors.append(
            Author(
                firstname=FIRST[(i * 7 + i // 51) % len(FIRST)],
                lastname=LAST[(i * 5) % len(LAST)],
                address=None if i % 11 == 0 else f"{rng.randrange(1, 200)} {rng.choice(STREETS)}",
                zipcode=None if i % 13 == 0 else rng.randrange(10000, 99999),
                telephone=None if i % 7 == 0 else f"+40 7{rng.randrange(10, 99)} {rng.randrange(100000, 999999)}",
                joindate=_d(rng, date(2010, 1, 1), date(2018, 12, 31)),
                popularity_score=score,
            )
        )
    # make sure "firstname starts with A and score >= 8" has answers
    for i in (0, 1, 2, 3, 4):
        authors[i].firstname = FIRST[i]
        authors[i].popularity_score = 8 + (i % 3)
    Author.objects.bulk_create(authors)
    authors = list(Author.objects.all())

    # self FK: some authors were recommended by an earlier author, many by nobody
    for i, a in enumerate(authors):
        if i and rng.random() < 0.6:
            a.recommendedby = authors[rng.randrange(0, i)]
    Author.objects.bulk_update(authors, ["recommendedby"])

    # one-to-one, deliberately not for every author
    profiles = [
        AuthorProfile(
            author=a,
            bio=f"{a.firstname} {a.lastname} writes from {rng.choice(CITIES)}.",
            website=None if i % 5 == 0 else f"https://{a.lastname.lower()}.example.com",
            newsletter_subscribers=rng.randrange(0, 40000),
        )
        for i, a in enumerate(authors)
        if i % 7 != 5
    ]
    AuthorProfile.objects.bulk_create(profiles)

    # M2M followers; a handful of authors are very popular (> 216 followers)
    through = Author.followers.through
    links = []
    for i, a in enumerate(authors):
        if i % 37 == 0:
            n = rng.randrange(217, 256)
        elif i % 3 == 0:
            n = rng.randrange(40, 140)
        else:
            n = rng.randrange(0, 25)
        for u in rng.sample(users, n):
            links.append(through(author_id=a.pk, user_id=u.pk))
    through.objects.bulk_create(links)

    # --- publishers --------------------------------------------------------
    pubs = []
    for i in range(20):
        pubs.append(
            Publisher(
                firstname=FIRST[(i * 11) % len(FIRST)],
                lastname=LAST[(i * 5) % len(LAST)],
                joindate=_d(rng, date(2010, 1, 1), date(2018, 12, 31)),
                popularity_score=rng.randrange(1, 11),
                country=COUNTRIES[i % len(COUNTRIES)],
            )
        )
    Publisher.objects.bulk_create(pubs)
    pubs = list(Publisher.objects.all())
    for i, p in enumerate(pubs):
        if i and rng.random() < 0.5:
            p.recommendedby = pubs[rng.randrange(0, i)]
    Publisher.objects.bulk_update(pubs, ["recommendedby"])

    series = [
        Series(name=f"The {rng.choice(ADJ)} {rng.choice(NOUN)} Cycle", publisher=rng.choice(pubs))
        for _ in range(12)
    ]
    Series.objects.bulk_create(series)
    series = list(Series.objects.all())

    # --- books -------------------------------------------------------------
    # skewed author distribution so some authors have > 10 books
    weights = [12 if i < 15 else 4 if i < 50 else 1 for i in range(len(authors))]
    used_titles, books = set(), []
    for i in range(700):
        title = f"{rng.choice(ADJ)} {rng.choice(NOUN)}"
        if title in used_titles and rng.random() < 0.85:
            title = f"{title} {rng.choice(['II', 'III', 'Revisited', 'Notebook'])}"
        used_titles.add(title)
        pub = rng.choice(pubs)
        cand = [s for s in series if s.publisher_id == pub.pk]
        books.append(
            Book(
                title=title,
                genre=rng.choice(GENRES),
                price=None if i % 23 == 0 else rng.randrange(5, 61),
                published_date=_d(rng, date(1995, 1, 1), date(2024, 6, 30)),
                page_count=rng.randrange(80, 900),
                author=None if i % 17 == 0 else rng.choices(authors, weights)[0],
                publisher=pub,
                series=rng.choice(cand) if cand and rng.random() < 0.4 else None,
            )
        )
    Book.objects.bulk_create(books)
    books = list(Book.objects.all())

    contrib = Book.contributors.through
    rows = []
    for b in books:
        for a in rng.sample(authors, rng.choices([0, 1, 2, 3], [45, 30, 15, 10])[0]):
            if a.pk != b.author_id:
                rows.append(contrib(book_id=b.pk, author_id=a.pk))
    contrib.objects.bulk_create(rows, ignore_conflicts=True)

    # --- stores ------------------------------------------------------------
    stores = [Store(name=f"{c} Books", city=c) for c in CITIES]
    Store.objects.bulk_create(stores)
    stores = list(Store.objects.all())
    stock = []
    for s in stores:
        for b in rng.sample(books, rng.randrange(60, 141)):
            stock.append(
                StoreStock(
                    store=s, book=b, quantity=rng.randrange(0, 30),
                    shelf=f"{rng.choice('ABCDEF')}{rng.randrange(1, 9)}",
                )
            )
    StoreStock.objects.bulk_create(stock)

    # --- reviews / orders --------------------------------------------------
    rev_weights = [8 if i % 11 == 0 else 1 for i in range(len(books))]
    reviews = [
        Review(
            book=rng.choices(books, rev_weights)[0],
            user=rng.choice(users),
            rating=rng.choices([1, 2, 3, 4, 5], [5, 10, 25, 35, 25])[0],
            text=rng.choice(REVIEW_TEXT),
            created=_d(rng, date(2019, 1, 1), date(2024, 12, 31)),
            upvotes=rng.choices([0, 1, 2, 5, 12, 40], [40, 20, 15, 12, 8, 5])[0],
        )
        for _ in range(1200)
    ]
    Review.objects.bulk_create(reviews)

    orders, items = [], []
    for _ in range(400):
        orders.append(
            Order(
                user=rng.choice(users),
                created=_d(rng, date(2022, 1, 1), date(2024, 12, 31)),
                status=rng.choices(["new", "paid", "shipped", "cancelled"], [15, 35, 40, 10])[0],
            )
        )
    Order.objects.bulk_create(orders)
    orders = list(Order.objects.all())
    for o in orders:
        for b in rng.sample(books, rng.randrange(1, 6)):
            items.append(
                OrderItem(order=o, book=b, quantity=rng.randrange(1, 4), unit_price=b.price or 20)
            )
    OrderItem.objects.bulk_create(items)

    # --- generic tags ------------------------------------------------------
    Tag.objects.bulk_create([Tag(name=n) for n in TAGS])
    tags = list(Tag.objects.all())
    ct_book = ContentType.objects.get_for_model(Book)
    ct_author = ContentType.objects.get_for_model(Author)
    tagged = []
    for b in rng.sample(books, 300):
        for t in rng.sample(tags, rng.randrange(1, 4)):
            tagged.append(TaggedItem(tag=t, content_type=ct_book, object_id=b.pk))
    for a in rng.sample(authors, 90):
        for t in rng.sample(tags, rng.randrange(1, 3)):
            tagged.append(TaggedItem(tag=t, content_type=ct_author, object_id=a.pk))
    TaggedItem.objects.bulk_create(tagged)

    counts = {
        "User": User.objects.count(), "Author": Author.objects.count(),
        "AuthorProfile": AuthorProfile.objects.count(), "Publisher": Publisher.objects.count(),
        "Series": Series.objects.count(), "Book": Book.objects.count(),
        "Store": Store.objects.count(), "StoreStock": StoreStock.objects.count(),
        "Review": Review.objects.count(), "Order": Order.objects.count(),
        "OrderItem": OrderItem.objects.count(), "Tag": Tag.objects.count(),
        "TaggedItem": TaggedItem.objects.count(),
        "Author.followers": through.objects.count(),
        "Book.contributors": contrib.objects.count(),
    }
    if verbose:
        for k, v in counts.items():
            print(f"  {k:<20} {v}")
    return counts
