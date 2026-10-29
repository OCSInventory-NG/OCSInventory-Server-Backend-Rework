import csv
import datetime
import os

from accountinfo.legacy_import import (
    REPORT_COLUMNS,
    LegacyAccountinfoImport,
    LegacyDatabase,
    LegacyError,
)
from django.core.management.base import BaseCommand, CommandError

BATCH_MIN, BATCH_MAX = 1, 10000


class Command(BaseCommand):
    """Import the accountinfo of an OCS 2.X database into the 3.x assets."""

    help = (
        "Read the accountinfo of a legacy OCS 2.X database (read only), create "
        "the missing definitions and copy the values of each legacy machine "
        "into its 3.x asset"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--legacy-url",
            required=True,
            help="mysql://user:password@host:3306/ocsweb, the password may come "
            "from OCS_LEGACY_PASSWORD instead",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Write nothing in the 3.x database, report the same",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace the 3.x values already set",
        )
        parser.add_argument(
            "--definitions-only",
            action="store_true",
            help="Only create the definitions and their list values",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Legacy machines written per transaction (default 500)",
        )
        parser.add_argument(
            "--report",
            help="Detailed CSV report, ./accountinfo-migration-<date>.csv by default",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if not BATCH_MIN <= batch_size <= BATCH_MAX:
            raise CommandError(
                f"--batch-size must be between {BATCH_MIN} and {BATCH_MAX}",
                returncode=1,
            )

        try:
            legacy = LegacyDatabase.from_url(
                options["legacy_url"], password=os.getenv("OCS_LEGACY_PASSWORD")
            )
        except ValueError as e:
            raise CommandError(f"--legacy-url: {e}", returncode=1)
        except LegacyError as e:
            raise CommandError(str(e), returncode=2)

        path = self.report_path(options["report"])
        try:
            with open(path, "w", newline="", encoding="utf-8") as stream:
                report = csv.DictWriter(stream, REPORT_COLUMNS, delimiter=";")
                report.writeheader()
                importer = LegacyAccountinfoImport(
                    legacy,
                    report,
                    dry_run=options["dry_run"],
                    overwrite=options["overwrite"],
                    definitions_only=options["definitions_only"],
                    batch_size=batch_size,
                    progress=self.progress(options["verbosity"]),
                )
                try:
                    result = importer.run()
                except LegacyError as e:
                    raise CommandError(str(e), returncode=2)
                except Exception as e:
                    raise CommandError(f"import failed: {e}", returncode=3)
        finally:
            legacy.close()

        self.summary(result, options, path)
        if result.failed_batch:
            raise CommandError(
                f"batch {result.failed_batch} failed and was rolled back, the "
                f"previous batches are written: {result.error}",
                returncode=3,
            )

    def progress(self, verbosity):
        if verbosity < 2:
            return None
        return lambda message: self.stdout.write(message)

    @staticmethod
    def report_path(path):
        """Never replace an existing report, suffix it -1, -2... instead"""
        if not path:
            path = f"./accountinfo-migration-{datetime.date.today().isoformat()}.csv"
        base, extension = os.path.splitext(path)
        candidate, suffix = path, 0
        while os.path.exists(candidate):
            suffix += 1
            candidate = f"{base}-{suffix}{extension}"
        return candidate

    def summary(self, result, options, path):
        number = self.number
        version = f"schema {result.version}" if result.version else "unknown version"
        mode = " - DRY RUN, nothing written" if options["dry_run"] else ""
        self.stdout.write(
            f"Legacy database: {result.label} ({version}) - read only{mode}"
        )

        definitions = result.definitions
        line = (
            f"Definitions: {number(definitions['created'])} created, "
            f"{number(definitions['existing'])} existing, "
            f"{number(definitions['ignored'])} ignored"
        )
        if result.ignored_reasons:
            line += f" ({', '.join(sorted(set(result.ignored_reasons)))})"
        self.stdout.write(line)

        if options["definitions_only"]:
            self.stdout.write("Machines: skipped (--definitions-only)")
        else:
            machines = result.machines
            by_deviceid = machines["deviceid"]
            by_rules = sum(
                count
                for rule, count in machines.items()
                if rule.startswith("duplicate:")
            )
            self.stdout.write(
                f"Machines: {number(by_deviceid + by_rules)} matched "
                f"({number(by_deviceid)} by DEVICEID, {number(by_rules)} by "
                f"duplicate rules), {number(machines['unmatched'])} unmatched, "
                f"{number(machines['duplicate'])} duplicates"
            )

            values = result.values
            line = (
                f"Values: {number(values['imported'])} imported, "
                f"{number(values['kept'])} kept (existing), "
                f"{number(values['rejected'])} rejected"
            )
            if options["overwrite"]:
                line += f", {number(values['overwritten'])} overwritten"
            self.stdout.write(line)

        self.stdout.write(
            f"SNMP accountinfo: {number(result.snmp_fields)} fields, "
            f"{number(result.snmp_devices)} devices - not migrated"
        )
        self.stdout.write(f"Report: {path}")

    @staticmethod
    def number(value):
        return f"{value:,}".replace(",", " ")
