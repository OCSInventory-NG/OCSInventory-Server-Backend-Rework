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

# Used to (re)generate tools/ocsinventory-backend-api-references.yaml,
# see .github/workflows/openapi-schema.yml
INSTALLED_APPS = INSTALLED_APPS + ["drf_spectacular"]  # noqa: F405
SPECTACULAR_SCHEMA_CLASS = "drf_spectacular.openapi.AutoSchema"
REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = SPECTACULAR_SCHEMA_CLASS  # noqa: F405
SPECTACULAR_SETTINGS = {
    "TITLE": "OCS Inventory Backend API References",
    "VERSION": "3.0.0",
}
