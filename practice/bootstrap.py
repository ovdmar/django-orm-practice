"""Spin up Django against an in-memory SQLite DB and fill it with data."""

import django
from django.conf import settings


def setup_django():
    if settings.configured:
        return
    settings.configure(
        DEBUG=True,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=["django.contrib.contenttypes", "bookstore"],
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        USE_TZ=False,
        TIME_ZONE="UTC",
        LOGGING_CONFIG=None,
    )
    django.setup()


def build_database(verbose=False):
    """Create the schema in the in-memory DB and seed it. Idempotent per process."""
    setup_django()
    from django.core.management import call_command

    call_command("migrate", run_syncdb=True, verbosity=0, interactive=False)
    from practice import seed

    return seed.seed(verbose=verbose)
