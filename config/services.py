import platform
from importlib.metadata import PackageNotFoundError, version

from auth.auth_method.models import AuthMethod
from config.models import Config
from config.serializers import ConfigSerializer
from django.conf import settings


class ServerInfoService:
    LIBRARY_PACKAGE_CANDIDATES = {
        "django": ("django",),
        "djangorestframework": ("djangorestframework",),
        "psycopg": ("psycopg", "psycopg2-binary", "psycopg2"),
    }

    DATABASE_ENGINES = {
        "django.db.backends.postgresql": "PostgreSQL",
        "django.db.backends.postgresql_psycopg2": "PostgreSQL",
        "django.db.backends.mysql": "MySQL",
        "django.db.backends.sqlite3": "SQLite",
        "django.db.backends.oracle": "Oracle",
    }

    @classmethod
    def get_server_info(cls):
        operating_system, operating_system_version = cls.get_operating_system_info()
        return {
            "authentication_type": cls.get_authentication_types(),
            "infrastructure_type": cls.get_infrastructure_type(),
            "operating_system": operating_system,
            "operating_system_version": operating_system_version,
            "orm_db_type": cls.get_database_type(),
            "ocs_configuration": cls.get_ocs_configuration(),
            "python_version": cls.get_python_version(),
            "python_libs_version": cls.get_python_libraries_version(),
        }

    @staticmethod
    def get_authentication_types():
        auth_methods = AuthMethod.objects.filter(enabled=True).order_by("priority", "name")
        return list(auth_methods.values_list("name", flat=True))

    @staticmethod
    def get_infrastructure_type():
        frontend_redirect = getattr(settings, "FRONTEND_REDIRECT", None)
        if frontend_redirect:
            return "split"
        return "standalone"

    @staticmethod
    def get_operating_system_info():
        try:
            os_release = platform.freedesktop_os_release()
        except (AttributeError, OSError):
            os_release = {}

        operating_system = (
            os_release.get("NAME")
            or os_release.get("PRETTY_NAME")
            or platform.system()
            or None
        )
        operating_system_version = (
            os_release.get("VERSION_ID") or os_release.get("VERSION") or None
        )

        return operating_system, operating_system_version

    @classmethod
    def get_database_type(cls):
        database_config = settings.DATABASES.get("default", {})
        engine = database_config.get("ENGINE")
        if not engine:
            return None

        database_label = cls.DATABASE_ENGINES.get(engine)
        if not database_label:
            database_label = engine.rsplit(".", 1)[-1].replace("_", " ").title()

        return f"Django ORM / {database_label}"

    @staticmethod
    def get_ocs_configuration():
        queryset = Config.objects.all()
        serializer = ConfigSerializer(queryset, many=True)
        return serializer.data if serializer.data else {}

    @staticmethod
    def get_python_version():
        return platform.python_version() or None

    @classmethod
    def get_python_libraries_version(cls):
        versions = {}
        for library_name, package_candidates in cls.LIBRARY_PACKAGE_CANDIDATES.items():
            versions[library_name] = None
            for package_name in package_candidates:
                try:
                    versions[library_name] = version(package_name)
                    break
                except PackageNotFoundError:
                    continue
        return versions
