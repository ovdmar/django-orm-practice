"""Schema for the ORM practice playground.

The first four models (User, Author, Publisher, Book) mirror the models from
the plainenglish.io "Django ORM examples and practice problems" article, field
names included, so the article's 40 problems can be solved verbatim.  The rest
exist to make select_related / prefetch_related interesting: a one-to-one, a
through-M2M, several reverse FKs, a self FK and a generic relation.
"""

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class User(models.Model):
    username = models.CharField(max_length=100)
    email = models.CharField(max_length=100)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.username


class Author(models.Model):
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    address = models.CharField(max_length=200, null=True, blank=True)
    zipcode = models.IntegerField(null=True, blank=True)
    telephone = models.CharField(max_length=100, null=True, blank=True)
    recommendedby = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="recommended"
    )
    joindate = models.DateField()
    popularity_score = models.IntegerField(default=0)
    followers = models.ManyToManyField(User, related_name="following", blank=True)
    tags = GenericRelation("TaggedItem")

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.firstname} {self.lastname}"


class AuthorProfile(models.Model):
    """One-to-one target: good for select_related in both directions."""

    author = models.OneToOneField(Author, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField()
    website = models.CharField(max_length=200, null=True, blank=True)
    newsletter_subscribers = models.IntegerField(default=0)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"profile of {self.author_id}"


class Publisher(models.Model):
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    recommendedby = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="recommended"
    )
    joindate = models.DateField()
    popularity_score = models.IntegerField(default=0)
    country = models.CharField(max_length=50, default="US")

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.firstname} {self.lastname}"


class Series(models.Model):
    name = models.CharField(max_length=100)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="series")

    class Meta:
        ordering = ["pk"]
        verbose_name_plural = "series"

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=100)
    genre = models.CharField(max_length=200)
    price = models.IntegerField(null=True, blank=True)
    published_date = models.DateField()
    page_count = models.IntegerField(default=200)
    author = models.ForeignKey(
        Author, null=True, blank=True, on_delete=models.SET_NULL, related_name="books"
    )
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="books")
    series = models.ForeignKey(
        Series, null=True, blank=True, on_delete=models.SET_NULL, related_name="books"
    )
    contributors = models.ManyToManyField(Author, related_name="contributed_books", blank=True)
    tags = GenericRelation("TaggedItem")

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.title


class Store(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    books = models.ManyToManyField(Book, through="StoreStock", related_name="stores")

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.name


class StoreStock(models.Model):
    """Explicit through model: prefetching these is not the same as the M2M."""

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="stock")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="stock")
    quantity = models.IntegerField(default=0)
    shelf = models.CharField(max_length=20, default="A1")

    class Meta:
        ordering = ["pk"]
        unique_together = [("store", "book")]


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField()
    text = models.CharField(max_length=200)
    created = models.DateField()
    upvotes = models.IntegerField(default=0)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.rating}* on {self.book_id}"


class Order(models.Model):
    STATUSES = [("new", "new"), ("paid", "paid"), ("shipped", "shipped"), ("cancelled", "cancelled")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    created = models.DateField()
    status = models.CharField(max_length=20, choices=STATUSES, default="new")

    class Meta:
        ordering = ["pk"]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="order_items")
    quantity = models.IntegerField(default=1)
    unit_price = models.IntegerField(default=0)

    class Meta:
        ordering = ["pk"]


class Tag(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.name


class TaggedItem(models.Model):
    """Generic relation: tags attach to both books and authors."""

    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="tagged_items")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        ordering = ["pk"]
        indexes = [models.Index(fields=["content_type", "object_id"])]
