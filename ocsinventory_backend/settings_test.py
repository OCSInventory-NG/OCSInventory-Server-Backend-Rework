"""Settings used to run the test suite (pytest-django).

Overrides the database backend with in-memory SQLite so tests don't
require a running PostgreSQL/MySQL server.
"""

from ocsinventory_backend.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
