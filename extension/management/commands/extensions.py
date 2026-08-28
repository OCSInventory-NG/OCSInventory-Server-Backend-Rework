"""Command-line lifecycle for the extensions present in the addons folder.

The **folder name** under ``settings.EXTENSIONS_DIR`` is the reference: it is
what ``settings.py`` uses to build INSTALLED_APPS, and the only identifier
available before the database is reachable. The Django app label is read from
the app registry rather than assumed, since an AppConfig may declare its own.
"""

import argparse
import json
import logging
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
    DjangoHelpFormatter,
)
from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from extension.models import Extension
from extension.sync import sync_extensions_from_filesystem
from ocsinventory_backend.ocs_framework.logmanager import DynamicLogLevelManager

LOGGER_NAME = "mgmt.management.commands"
APP_PREFIX = "extensions."
HEADERS = ("FOLDER", "MANIFEST", "DB", "ENABLED", "STATUS")


def _manifest(folder_path):
    """Manifest of one extension, or None when it cannot be trusted."""
    path = folder_path / "extension.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("name") else None


def _scan():
    """Join the three places an extension exists, keyed by folder name.

    A folder may be missing from any of them: present on disk but never
    registered, registered but no longer on disk, and so on.
    """
    root = Path(settings.EXTENSIONS_DIR)
    folders = (
        {entry.name for entry in root.iterdir() if entry.is_dir()}
        if root.exists()
        else set()
    )
    labels = {
        config.name.removeprefix(APP_PREFIX): config.label
        for config in apps.get_app_configs()
        if config.name.startswith(APP_PREFIX)
    }
    rows = {row.django_app: row for row in Extension.objects.all()}

    return {
        folder: {
            "folder": folder,
            "on_disk": folder in folders,
            "label": labels.get(folder),
            "manifest": _manifest(root / folder) if folder in folders else None,
            "row": rows.get(folder),
        }
        for folder in sorted(folders | set(labels) | set(rows))
    }


def _status(state):
    """One-line state, most blocking condition first."""
    if not state["on_disk"]:
        return "orphan (no folder)"
    if state["manifest"] is None:
        return "no usable extension.json"
    if state["label"] is None:
        return "not loaded by Django"
    if state["label"] != state["folder"]:
        return f"app label '{state['label']}' differs from the folder"
    if state["row"] is None:
        return "not registered"
    return "ok"


def _migration_state(label):
    """Migration state of one app label.

    ``migrate --check`` only answers the question globally. The forwards plan
    also drags in cross-app dependencies (proxmoxapi depends on
    inventory_base), which must never be charged to the extension.

    ``has_migrations`` is the trap this separates out: an app whose migration
    files are absent has nothing to apply and creates no table, which would
    otherwise be indistinguishable from being up to date.
    """
    executor = MigrationExecutor(connection)
    loader = executor.loader

    # not unmigrated_apps: a folder keeping an empty migrations/ package is
    # still a "migrated app" for Django, with zero migration in the graph
    if not any(node[0] == label for node in loader.graph.nodes):
        return {"has_migrations": False, "unapplied": [], "blocking": []}

    own, blocking = [], []
    for migration, backwards in executor.migration_plan(
        loader.graph.leaf_nodes(label)
    ):
        if backwards:
            continue
        if migration.app_label == label:
            own.append(migration.name)
        else:
            blocking.append(f"{migration.app_label}.{migration.name}")
    return {"has_migrations": True, "unapplied": own, "blocking": blocking}


def _has_models(label):
    """True when the app declares models, so it needs migrations to be usable."""
    return bool(apps.get_app_config(label).get_models())


def _missing_tables(label):
    """Tables the app's models declare but that do not exist in the database.

    The migration history says what was recorded as applied; this says what is
    actually there. They diverge when the recorded history no longer matches
    the migration files -- two extensions claiming the same app label, or
    tables dropped outside Django.
    """
    expected = {
        model._meta.db_table
        for model in apps.get_app_config(label).get_models()
        if model._meta.managed
    }
    if not expected:
        return []
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
    return sorted(expected - existing)


def _orphan_tables(label):
    with connection.cursor() as cursor:
        names = connection.introspection.table_names(cursor)
    return sorted(name for name in names if name.startswith(f"{label}_"))


class Command(BaseCommand):
    """Inspect and manage the extensions installed on this server."""

    help = "Inspect and manage installed extensions"

    LOG_LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

    def add_arguments(self, parser):
        parser.add_argument(
            "--loglevel",
            choices=self.LOG_LEVELS,
            help="Override logging level from server",
        )
        # repeated on every sub-parser so --loglevel is accepted on both sides
        # of the action name; SUPPRESS keeps the sub-parser from resetting a
        # value that was given before it
        common = CommandParser(add_help=False)
        common.add_argument(
            "--loglevel",
            choices=self.LOG_LEVELS,
            default=argparse.SUPPRESS,
            help="Override logging level from server",
        )

        sub = parser.add_subparsers(dest="action", required=True)

        def add(name, handler, description):
            # formatter_class is not inherited from the root parser
            action = sub.add_parser(
                name,
                parents=[common],
                formatter_class=DjangoHelpFormatter,
                help=description,
            )
            action.set_defaults(handler=handler)
            return action

        add("list", self.list_extensions, "List the extension folders and their state")

        for name, handler, description in (
            ("enable", self.enable, "Enable an extension (same action as the web UI)"),
            ("disable", self.disable, "Disable an extension"),
        ):
            add(name, handler, description).add_argument(
                "folder", help="Extension folder name"
            )

        install = add(
            "install", self.install, "Register an extension and apply its migrations"
        )
        install.add_argument("folder", help="Extension folder name")
        install.add_argument(
            "--enable", action="store_true", help="Enable it once installed"
        )

        check = add(
            "check-migrations",
            self.check_migrations,
            "Check the applied migration level against the code",
        )
        check.add_argument(
            "folder", nargs="?", help="Limit the check to this extension"
        )

        apply_migrations = add(
            "apply-migrations",
            self.apply_migrations,
            "Apply, or re-apply, the migrations of an extension",
        )
        apply_migrations.add_argument("folder", help="Extension folder name")
        apply_migrations.add_argument(
            "--redo",
            action="store_true",
            help="Unapply then re-apply; DESTROYS the extension data",
        )
        self._add_noinput(apply_migrations)

        uninstall = add(
            "uninstall",
            self.uninstall,
            "Disable an extension and remove it from the registry",
        )
        uninstall.add_argument("folder", help="Extension folder name")
        uninstall.add_argument(
            "--erase-data",
            action="store_true",
            help="Also unapply the migrations; DESTROYS the extension data",
        )
        self._add_noinput(uninstall)

        clean = add(
            "clean",
            self.clean,
            "Purge the leftovers of an extension whose folder is gone",
        )
        clean.add_argument("folder", help="Extension folder name")
        self._add_noinput(clean)

    def handle(self, *args, **options):
        logger = logging.getLogger(LOGGER_NAME)

        if options.get("loglevel"):
            DynamicLogLevelManager().set_level_for_logger(
                LOGGER_NAME, options["loglevel"]
            )
            logger.debug(f"Log level overridden to: {options['loglevel']}")

        logger.debug(f"Command arguments: {options}")
        return options["handler"](**options)

    @staticmethod
    def _add_noinput(parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do not prompt for confirmation",
        )

    def _confirm(self, warning, options):
        """Ask before a destructive step, unless --noinput was given."""
        if not options.get("interactive", True):
            return
        self.stdout.write(self.style.WARNING(warning))
        if input("Type 'yes' to continue: ") != "yes":
            raise CommandError("Aborted.", returncode=1)

    def _state(self, folder):
        state = _scan().get(folder)
        if state is None:
            raise CommandError(f"Unknown extension: {folder}", returncode=1)
        return state

    def _label(self, state):
        """App label to hand to migrate, which must equal the folder name.

        ``settings.py`` keys INSTALLED_APPS on the folder, ``urls.py`` mounts
        on ``django_app``, and ``clean`` has nothing but the folder name left
        once the code is gone. An AppConfig declaring its own label breaks that
        chain silently, so it is refused rather than half-supported.
        """
        folder = state["folder"]
        if state["label"] is None:
            raise CommandError(
                f"{folder}: {_status(state)} -- no app label to migrate. Check "
                "that the folder has an __init__.py and imports cleanly, then "
                "restart the server.",
                returncode=1,
            )
        if state["label"] != folder:
            raise CommandError(
                f"{folder}: its AppConfig declares label '{state['label']}'. An "
                "extension must let Django derive the label from its folder "
                "name; remove the 'label' attribute from the AppConfig.",
                returncode=1,
            )
        return state["label"]

    def _migrate(self, label, *args, **options):
        # resolves to mgmt.management.commands.migrate, which also creates the
        # permissions of the migrated app
        try:
            call_command(
                "migrate",
                label,
                *args,
                verbosity=options.get("verbosity", 1),
                stdout=self.stdout,
            )
        except DatabaseError as exc:
            # the usual cause is a table left behind by 'clean': migrate then
            # tries to create it again. Translated into a CommandError so a
            # script gets a usable message and exit code; 'manage.py
            # --traceback' still shows the original trace.
            raise CommandError(
                f"migrate {label} failed: {exc}\n"
                "If its tables were left behind by 'extensions clean', "
                f"'manage.py migrate {label} --fake' re-records the history "
                "without touching them.",
                returncode=1,
            ) from exc

    def _plan_unapply(self, label, options):
        """Refuse an unsafe unapply, confirm a destructive one.

        Returns False when nothing is applied. Read-only: no write happens
        before the caller acts on the answer.
        """
        executor = MigrationExecutor(connection)

        own, foreign = [], []
        for migration, backwards in executor.migration_plan([(label, None)]):
            if not backwards:
                continue
            if migration.app_label == label:
                own.append(migration.name)
            else:
                foreign.append(f"{migration.app_label}.{migration.name}")

        if foreign:
            raise CommandError(
                f"Refusing to unapply {label}: migrations of other apps depend "
                f"on it ({', '.join(foreign)}). Unapplying them would destroy "
                "unrelated data.",
                returncode=1,
            )
        if not own:
            return False

        self._confirm(
            f"About to unapply {len(own)} migration(s) of {label} and drop its "
            "tables. All of its data will be lost.",
            options,
        )
        return True

    # ------------------------------------------------------------------- list

    def list_extensions(self, **options):
        states = _scan()
        if not states:
            self.stdout.write("No extension folder found.")
            return

        rows = [
            (
                state["folder"],
                (state["manifest"] or {}).get("version") or "-",
                state["row"].version if state["row"] else "-",
                {True: "yes", False: "no"}[state["row"].enabled]
                if state["row"]
                else "-",
                _status(state),
            )
            for state in states.values()
        ]

        widths = [max(len(str(c)) for c in col) for col in zip(HEADERS, *rows)]
        for row in (HEADERS, *rows):
            line = "  ".join(str(c).ljust(w) for c, w in zip(row, widths))
            self.stdout.write(line.rstrip())

    # --------------------------------------------------------- enable/disable

    def enable(self, **options):
        self._set_enabled(options["folder"], True)

    def disable(self, **options):
        self._set_enabled(options["folder"], False)

    def _set_enabled(self, folder, enabled):
        state = self._state(folder)
        if state["row"] is None:
            raise CommandError(
                f"{folder} is not registered; run 'extensions install {folder}' "
                "first.",
                returncode=1,
            )

        # same write as the web UI toggle: PATCH extensions/<id>/ {enabled}
        Extension.objects.filter(pk=state["row"].pk).update(enabled=enabled)

        action = "enabled" if enabled else "disabled"
        self.stdout.write(self.style.SUCCESS(f"{folder} {action}."))
        # urls.py mounts the extension routes at import time, and the frontend
        # asks extensions/enabled/ once per page load
        self.stdout.write("Restart the application server to apply the change.")

    # ---------------------------------------------------------------- install

    def install(self, **options):
        folder = options["folder"]
        state = self._state(folder)

        if state["manifest"] is None:
            raise CommandError(
                f"{folder}: no usable extension.json ({_status(state)}); copy "
                "the extension folder into the addons directory first.",
                returncode=1,
            )
        label = self._label(state)

        # checked before the first write: sync_extensions_from_filesystem()
        # trusts the manifest, so a mismatch would leave a row keyed on a
        # folder that does not exist
        declared = state["manifest"].get("django_app")
        if declared and declared.removeprefix(APP_PREFIX) != folder:
            raise CommandError(
                f"{folder}: its extension.json declares django_app "
                f"'{declared}'. It must match the folder name.",
                returncode=1,
            )

        # reused unchanged: it upserts every manifest on disk, which is exactly
        # what post_migrate already does on each migrate
        sync_extensions_from_filesystem()

        state = self._state(folder)
        if state["row"] is None:
            raise CommandError(
                f"{folder}: the registry has no row for it after the sync.",
                returncode=1,
            )
        row = state["row"]
        self.stdout.write(f"{folder}: registered as '{row.name}' {row.version}")

        migrations = _migration_state(label)
        self._migrate(label, **options)

        missing = _missing_tables(label)
        if missing:
            raise CommandError(
                f"{folder}: migrate reported success but {len(missing)} table(s) "
                f"are missing ({', '.join(missing)}). Its migration history is "
                "recorded but does not match its migration files -- most often "
                "another extension already used the app label "
                f"'{label}'. Run 'extensions check-migrations {folder}'.",
                returncode=1,
            )

        if not migrations["has_migrations"] and _has_models(label):
            self.stdout.write(
                self.style.WARNING(
                    f"{folder} has no migration file, so no table was created. "
                    f"Run 'manage.py makemigrations {label}' then "
                    f"'manage.py extensions apply-migrations {folder}'."
                )
            )

        if options.get("enable"):
            self._set_enabled(folder, True)
        elif not row.enabled:
            # install never disables anything, so only say so when it is true
            self.stdout.write(
                f"{folder} is installed but disabled; run 'extensions enable "
                f"{folder}' to activate it."
            )

    # -------------------------------------------------------- check-migrations

    def check_migrations(self, **options):
        folder = options.get("folder")
        states = [self._state(folder)] if folder else list(_scan().values())
        if not states:
            self.stdout.write("No extension folder found.")
            return

        failed = []
        for state in states:
            name = state["folder"]
            # covers both "Django never loaded it" and an AppConfig declaring
            # its own label, which _label() refuses everywhere else
            if state["label"] != name:
                self.stdout.write(f"{name}: {_status(state)}")
                failed.append(name)
                continue

            label = state["label"]
            migrations = _migration_state(label)

            if not migrations["has_migrations"]:
                if not _has_models(label):
                    self.stdout.write(f"{name}: no migrations")
                    continue
                # the addons folder is not tracked by git, so a migration
                # cleanup leaves the models without any migration file
                self.stdout.write(
                    f"{name}: declares models but has no migration file, so "
                    "its tables were never created; run 'manage.py "
                    f"makemigrations {label}'"
                )
                failed.append(name)
                continue

            unapplied = migrations["unapplied"]
            if not unapplied:
                missing = _missing_tables(label)
                if not missing:
                    self.stdout.write(f"{name}: up to date")
                    continue
                # the ticket asks to check against reality, not just against
                # django_migrations: the history can be recorded while the
                # tables it was supposed to create are not there
                self.stdout.write(
                    f"{name}: history says applied but {len(missing)} table(s) "
                    f"are missing ({', '.join(missing)})"
                )
                failed.append(name)
                continue

            failed.append(name)
            self.stdout.write(f"{name}: {len(unapplied)} migration(s) not applied")
            for migration in unapplied:
                self.stdout.write(f"  unapplied: {migration}")
            for migration in migrations["blocking"]:
                self.stdout.write(f"  blocked by: {migration}")

        if failed:
            raise CommandError(
                f"Migration state not clean for: {', '.join(failed)}", returncode=1
            )

    # -------------------------------------------------------- apply-migrations

    def apply_migrations(self, **options):
        state = self._state(options["folder"])
        label = self._label(state)

        if options.get("redo"):
            if not self._plan_unapply(label, options):
                self.stdout.write(f"{label}: nothing applied, nothing to redo")
                return
            self._migrate(label, "zero", **options)

        self._migrate(label, **options)

    # -------------------------------------------------------------- uninstall

    def uninstall(self, **options):
        folder = options["folder"]
        state = self._state(folder)
        if state["row"] is None:
            raise CommandError(f"{folder} is not registered.", returncode=1)

        # everything that can refuse or be cancelled runs before the first
        # write, so an aborted uninstall leaves no side effect behind
        erase = False
        if options.get("erase_data"):
            erase = self._plan_unapply(self._label(state), options)

        Extension.objects.filter(pk=state["row"].pk).update(enabled=False)
        self.stdout.write(f"{folder}: disabled")

        if erase:
            self._migrate(state["label"], "zero", **options)

        # after the migrations, never before: migrate emits post_migrate, which
        # syncs the manifests again and would recreate the row
        Extension.objects.filter(pk=state["row"].pk).delete()
        self.stdout.write(f"{folder}: removed from the registry")

        if state["on_disk"]:
            self.stdout.write(
                self.style.WARNING(
                    f"The code is still in {Path(settings.EXTENSIONS_DIR) / folder}\n"
                    "Remove that folder to complete the uninstall: while it is "
                    "there, the next 'manage.py migrate' registers the extension "
                    "again (disabled)."
                )
            )

    # ------------------------------------------------------------------ clean

    def clean(self, **options):
        folder = options["folder"]
        state = self._state(folder)

        if state["on_disk"]:
            raise CommandError(
                f"{folder} is still on disk; clean only handles an extension "
                "whose folder was removed without a proper uninstall. Use "
                f"'extensions uninstall {folder}' instead.",
                returncode=1,
            )

        # the code is gone, so there is no AppConfig left to read the label
        # from: the folder name is all we have, and it is the reference anyway
        tables = _orphan_tables(folder)

        self._confirm(
            f"About to remove {folder} from the registry and delete its "
            f"migration history. The {len(tables)} table(s) left behind will "
            "NOT be dropped.",
            options,
        )

        if state["row"] is not None:
            Extension.objects.filter(pk=state["row"].pk).delete()
            self.stdout.write(f"{folder}: removed from the registry")

        deleted, _ = MigrationRecorder.Migration.objects.filter(app=folder).delete()
        self.stdout.write(f"{folder}: {deleted} migration history row(s) deleted")

        if tables:
            self.stdout.write(
                self.style.WARNING(
                    "Tables left in the database (not dropped):\n  "
                    + "\n  ".join(tables)
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "Reinstalling will FAIL while they exist: migrate would try "
                    f"to create them again. 'manage.py migrate {folder} --fake' "
                    "re-records the history without touching them."
                )
            )
        # clean cannot unapply anything, so the reverse data migrations never
        # ran: rows the extension wrote into other apps' tables survive too,
        # and no prefix can find them
        self.stdout.write(
            self.style.WARNING(
                f"Only the '{folder}_' prefix was inspected. Because clean "
                "never unapplies, anything this extension's data migrations "
                "wrote into other apps' tables is still in the database, and "
                "a model with an explicit db_table is not listed either."
            )
        )
