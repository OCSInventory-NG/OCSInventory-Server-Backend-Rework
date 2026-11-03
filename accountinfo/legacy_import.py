"""
Import of the administrative data (accountinfo) of an OCS 2.X database.

The legacy database is only read. Its definitions become ASSET configs, each
legacy machine is reconciled with one 3.x asset and its values are copied
into the accountdata of that asset, without replacing a value already set
unless asked to.
"""

import datetime
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote, urlparse

from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from asset.inventory_base.models import InventoryBase
from asset.services import ReconciliationService
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

LOGGER = logging.getLogger("mgmt.management.commands.ImportLegacyAccountinfo")

ASSET_SLUG = "inventory_base.inventorybase"

# accountinfo_config.TYPE of ocsreports 2.12 ($type_accountinfo)
TEXT, TEXTAREA, SELECT, CHECKBOX, RADIOBUTTON, DATE, NUMBER = 0, 1, 2, 5, 11, 14, 15

LEGACY_TYPES = {
    TEXT: "TEXT",
    TEXTAREA: "TEXTAREA",
    SELECT: "SELECT",
    RADIOBUTTON: "SELECT",
    CHECKBOX: "CHECKBOX",
    DATE: "TEXT",
    NUMBER: "TEXT",
}

LIST_TYPES = ("SELECT", "CHECKBOX")
TEXT_TYPES = ("TEXT", "TEXTAREA")

# hardware rows that are groups, not machines
GROUP_DEVICEIDS = ("_SYSTEMGROUP_", "_DOWNLOADGROUP_")

CHECKBOX_SEPARATOR = "&&&"

# fields of legacy_duplicate_reconciliation the legacy database can feed
RULE_FIELDS = ("name", "serial")

NAME_MAX = AccountinfoConfig._meta.get_field("name").max_length
DESCRIPTION_MAX = AccountinfoConfig._meta.get_field("description").max_length
VALUE_MAX = AccountinfoValue._meta.get_field("value").max_length

REPORT_COLUMNS = (
    "scope",
    "legacy_hardware_id",
    "legacy_name",
    "deviceid",
    "asset_id",
    "match_rule",
    "field",
    "legacy_value",
    "v3_value_before",
    "status",
    "reason",
)


class LegacyError(Exception):
    """The legacy database cannot be reached or read"""


class Rejected(ValueError):
    """A legacy value that does not fit its 3.x config"""


class LegacyDatabase:
    """
    Read-only access to an OCS 2.X database

    Wraps any DB-API connection: MySQL / MariaDB in production, sqlite in the
    tests. Queries take no parameters, the only values put in them are the
    integer ids read from the legacy database itself.
    """

    SCHEMES = ("mysql", "mariadb")

    def __init__(self, connection, label="legacy"):
        self.connection = connection
        self.label = label

    @classmethod
    def from_url(cls, url, password=None):
        """Open a read-only session from mysql://user@host:3306/base"""
        parsed = urlparse(url)
        if parsed.scheme not in cls.SCHEMES or not parsed.path.strip("/"):
            raise ValueError("expected mysql://user@host:3306/database")

        base = parsed.path.strip("/")
        host = parsed.hostname or "localhost"
        settings = {
            "host": host,
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or "") or password or "",
            "database": base,
            "charset": "utf8mb4",
        }

        try:
            connection = cls._connect(settings)
            cursor = connection.cursor()
            cursor.execute("SET SESSION TRANSACTION READ ONLY")
            cursor.close()
        except LegacyError:
            raise
        except Exception as e:
            raise LegacyError(f"cannot connect to {base}@{host}: {e}") from e

        return cls(connection, label=f"{base}@{host}")

    @staticmethod
    def _connect(settings):
        """mysqlclient when installed, PyMySQL otherwise"""
        try:
            import MySQLdb
        except ImportError:
            MySQLdb = None

        if MySQLdb is not None:
            settings = dict(settings)
            settings["passwd"] = settings.pop("password")
            settings["db"] = settings.pop("database")
            return MySQLdb.connect(**settings)

        try:
            import pymysql
        except ImportError:
            raise LegacyError("no MySQL client installed (PyMySQL or mysqlclient)")
        return pymysql.connect(**settings)

    def close(self):
        self.connection.close()

    def rows(self, query):
        """Run a SELECT, return its rows as dicts"""
        cursor = self.execute(query)
        try:
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def columns(self, table):
        cursor = self.execute(f"SELECT * FROM {table} WHERE 1 = 0")
        try:
            return [column[0] for column in cursor.description]
        finally:
            cursor.close()

    def execute(self, query):
        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
        except Exception as e:
            cursor.close()
            raise LegacyError(f"cannot read the legacy database: {e}") from e
        return cursor

    def version(self):
        try:
            rows = self.rows("SELECT TVALUE FROM config WHERE NAME = 'GUI_VERSION'")
        except Exception:
            return None
        return rows[0]["TVALUE"] if rows else None

    def definitions(self):
        return self.rows(
            "SELECT ID, NAME, TYPE, ACCOUNT_TYPE, COMMENT FROM accountinfo_config "
            "ORDER BY ID"
        )

    def list_values(self):
        return self.rows(
            "SELECT NAME, IVALUE, TVALUE FROM config "
            "WHERE NAME LIKE 'ACCOUNT_VALUE_%' ORDER BY NAME"
        )

    def machines(self):
        groups = ", ".join(f"'{deviceid}'" for deviceid in GROUP_DEVICEIDS)
        return self.rows(
            "SELECT h.ID, h.DEVICEID, h.NAME, h.LASTDATE, b.SSN "
            "FROM hardware h LEFT JOIN bios b ON b.HARDWARE_ID = h.ID "
            f"WHERE h.DEVICEID NOT IN ({groups}) ORDER BY h.ID"
        )

    def accountinfo(self, hardware_ids):
        if not hardware_ids:
            return []
        ids = ", ".join(str(int(id)) for id in hardware_ids)
        return self.rows(f"SELECT * FROM accountinfo WHERE HARDWARE_ID IN ({ids})")

    def snmp_devices(self):
        try:
            return self.rows("SELECT COUNT(*) AS N FROM snmp_accountinfo")[0]["N"]
        except Exception:
            # the table predates some 2.X versions
            return 0


@dataclass
class Definition:
    """A legacy COMPUTERS field and the 3.x config it lands in"""

    legacy_id: int
    name: str
    legacy_type: int
    column: str
    config: Optional[AccountinfoConfig] = None
    # IVALUE -> AccountinfoValue
    values: dict = field(default_factory=dict)

    @property
    def is_list(self):
        return self.legacy_type in (SELECT, RADIOBUTTON, CHECKBOX)


@dataclass
class Machine:
    hardware_id: int
    deviceid: str
    name: str
    lastdate: object
    serial: str
    asset_id: Optional[int] = None
    rule: str = ""
    status: str = ""
    reason: str = ""


@dataclass
class Result:
    """What the run did, as the console prints it"""

    label: str = ""
    version: Optional[str] = None
    definitions: Counter = field(default_factory=Counter)
    ignored_reasons: list = field(default_factory=list)
    machines: Counter = field(default_factory=Counter)
    values: Counter = field(default_factory=Counter)
    snmp_fields: int = 0
    snmp_devices: int = 0
    failed_batch: Optional[int] = None
    error: str = ""


class LegacyAccountinfoImport:
    """
    Copy the accountinfo of a legacy database into the 3.x assets

    args:
        legacy: a LegacyDatabase
        report: a csv writer (or anything with writerow) for the detailed rows
        dry_run: run everything, then roll the 3.x database back
        overwrite: replace the 3.x values already set
        definitions_only: stop once the definitions are created
        batch_size: legacy machines written per transaction
    """

    class DryRun(Exception):
        """Raised at the end of a dry run to roll everything back"""

    def __init__(
        self,
        legacy,
        report,
        dry_run=False,
        overwrite=False,
        definitions_only=False,
        batch_size=500,
        progress=None,
    ):
        self.legacy = legacy
        self.report = report
        self.dry_run = dry_run
        self.overwrite = overwrite
        self.definitions_only = definitions_only
        self.batch_size = batch_size
        self.progress = progress or (lambda message: None)
        self.result = Result(label=legacy.label)
        self.content_type = ContentType.objects.get_for_model(InventoryBase)

    def run(self):
        self.result.version = self.legacy.version()

        if not self.dry_run:
            with transaction.atomic():
                definitions = self.import_definitions()
            if not self.definitions_only:
                self.import_values(definitions)
            return self.result

        # the definitions must exist for the values to point at them, so a
        # dry run keeps a single transaction and drops it at the very end
        try:
            with transaction.atomic():
                definitions = self.import_definitions()
                if not self.definitions_only:
                    self.import_values(definitions)
                raise self.DryRun()
        except self.DryRun:
            pass
        return self.result

    # ---- definitions ----

    def import_definitions(self):
        """Create the missing ASSET configs and list values (FR-001 to FR-004)"""
        legacy_rows = self.legacy.definitions()
        columns = set(self.legacy.columns("accountinfo"))
        labels = self.legacy_labels()

        definitions = []
        for row in legacy_rows:
            name = (row["NAME"] or "").strip()

            if row["ACCOUNT_TYPE"] == "SNMP":
                self.result.snmp_fields += 1
                self.definition_row(name, "ignored", "SNMP field, not migrated")
                continue
            if row["ACCOUNT_TYPE"] != "COMPUTERS":
                continue

            definition = self.make_definition(row, name, columns)
            if definition is None:
                continue

            self.attach_config(definition, row)
            if definition.is_list and definition.config.datatype in LIST_TYPES:
                self.attach_values(definition, labels.get(name, []))
            definitions.append(definition)

        self.result.snmp_devices = self.legacy.snmp_devices()
        LOGGER.info(f"Definitions: {dict(self.result.definitions)}")
        return definitions

    def make_definition(self, row, name, columns):
        legacy_type = self.as_int(row["TYPE"])
        column = "TAG" if name == "TAG" else f"fields_{row['ID']}"

        if legacy_type not in LEGACY_TYPES:
            return self.ignore(
                name, f"unsupported type {row['TYPE']}", f"type {row['TYPE']}"
            )
        if not name or len(name) > NAME_MAX:
            return self.ignore(name, f"name empty or over {NAME_MAX} characters")
        if len(row["COMMENT"] or "") > DESCRIPTION_MAX:
            return self.ignore(name, f"comment over {DESCRIPTION_MAX} characters")
        if column not in columns:
            return self.ignore(name, f"column {column} missing from accountinfo")

        return Definition(
            legacy_id=row["ID"], name=name, legacy_type=legacy_type, column=column
        )

    def ignore(self, name, reason, short=None):
        """Report a definition left out, short is its console summary"""
        self.result.definitions["ignored"] += 1
        self.result.ignored_reasons.append(short or reason)
        self.definition_row(name, "ignored", reason)
        return None

    def attach_config(self, definition, row):
        """Reuse the ASSET config of that name, create it otherwise"""
        config = AccountinfoConfig.objects.filter(
            name=definition.name, datatarget="ASSET"
        ).first()

        if config is not None:
            self.result.definitions["existing"] += 1
            self.definition_row(definition.name, "existing", "")
        else:
            config = AccountinfoConfig.objects.create(
                name=definition.name,
                description=(row["COMMENT"] or definition.name),
                datatype=LEGACY_TYPES[definition.legacy_type],
                datatarget="ASSET",
            )
            self.result.definitions["created"] += 1
            self.definition_row(definition.name, "created", "")

        definition.config = config

    def legacy_labels(self):
        """{field name: [(IVALUE, TVALUE), ...]} out of ACCOUNT_VALUE_<NAME>_<n>"""
        labels = defaultdict(list)
        for row in self.legacy.list_values():
            key = row["NAME"][len("ACCOUNT_VALUE_") :]
            name, _, suffix = key.rpartition("_")
            if not name or not suffix.isdigit():
                continue
            index = self.as_int(row["IVALUE"])
            labels[name].append(
                (int(suffix) if index is None else index, row["TVALUE"])
            )
        for values in labels.values():
            values.sort()
        return labels

    def attach_values(self, definition, labels):
        """Create the list values the config lacks, in the legacy order (FR-002)"""
        existing = {
            self.fold(value.value): value
            for value in definition.config.accountinfo_values.all()
        }

        for index, label in labels:
            label = (label or "").strip()
            if not label:
                continue
            if len(label) > VALUE_MAX:
                self.definition_row(
                    definition.name,
                    "ignored",
                    f"list value '{label[:40]}…' over {VALUE_MAX} characters",
                )
                continue

            value = existing.get(self.fold(label))
            if value is None:
                value = AccountinfoValue.objects.create(
                    accountinfo_config=definition.config, value=label
                )
                existing[self.fold(label)] = value
            definition.values[index] = value

    # ---- machines ----

    def match_machines(self):
        """Reconcile every legacy machine with at most one asset (FR-005)"""
        machines = [
            Machine(
                hardware_id=row["ID"],
                deviceid=row["DEVICEID"],
                name=row["NAME"],
                lastdate=row["LASTDATE"],
                serial=row["SSN"],
            )
            for row in self.legacy.machines()
        ]

        assets = list(InventoryBase.objects.values("id", "uuid", "name", "serial"))
        by_uuid = {asset["uuid"]: asset["id"] for asset in assets}
        indexes = {}
        fields = self.rule_fields()

        for machine in machines:
            if machine.deviceid in by_uuid:
                machine.asset_id = by_uuid[machine.deviceid]
                machine.rule = "deviceid"
                continue

            # a 2.X agent sent to the 3.x server may get a new DEVICEID, and a
            # virtual machine often has no serial: a blank field is left out
            # and the others still have to match
            values = {"name": machine.name, "serial": machine.serial}
            usable = tuple(name for name in fields if self.usable(values[name]))
            if not usable:
                machine.status = "unmatched"
                machine.reason = f"no usable value on {'+'.join(fields)}"
                continue

            if usable not in indexes:
                indexes[usable] = self.rule_index(assets, usable)
            candidates = indexes[usable].get(self.rule_key(values, usable), [])

            if len(candidates) == 1:
                machine.asset_id = candidates[0]
                machine.rule = "duplicate:" + "+".join(usable)
            elif candidates:
                machine.status = "duplicate"
                machine.reason = f"{len(candidates)} assets match on {'+'.join(usable)}"
            else:
                machine.status = "unmatched"
                machine.reason = f"no asset matches on {'+'.join(usable)}"

        self.settle_shared_assets(machines)

        for machine in machines:
            if machine.asset_id is not None:
                machine.status = "matched"
                self.result.machines[machine.rule] += 1
            else:
                self.result.machines[machine.status] += 1
                self.machine_row(machine)

        return [machine for machine in machines if machine.asset_id is not None]

    @staticmethod
    def settle_shared_assets(machines):
        """An asset claimed twice goes to the machine seen last (LASTDATE)"""
        claims = defaultdict(list)
        for machine in machines:
            if machine.asset_id is not None:
                claims[machine.asset_id].append(machine)

        for asset_id, claimants in claims.items():
            if len(claimants) < 2:
                continue

            dates = [LegacyAccountinfoImport.as_date(m.lastdate) for m in claimants]
            latest = max(dates)
            winners = [m for m, date in zip(claimants, dates) if date == latest]
            keep = winners[0] if len(winners) == 1 else None

            for machine in claimants:
                if machine is keep:
                    continue
                machine.status = "duplicate"
                machine.reason = (
                    f"asset {asset_id} given to legacy machine {keep.hardware_id}"
                    if keep
                    else f"asset {asset_id} claimed by machines with the same LASTDATE"
                )
                machine.asset_id = None

    @staticmethod
    def rule_fields():
        """legacy_duplicate_reconciliation, limited to what the legacy base holds"""
        configured = ReconciliationService.get_legacy_reconciliation_fields()
        fields = [name for name in configured if name in RULE_FIELDS]
        return fields or list(RULE_FIELDS)

    @classmethod
    def rule_index(cls, assets, fields):
        """{rule key: [asset ids]} over the assets usable on every field"""
        index = defaultdict(list)
        for asset in assets:
            if all(cls.usable(asset[name]) for name in fields):
                index[cls.rule_key(asset, fields)].append(asset["id"])
        return index

    @staticmethod
    def usable(value):
        if isinstance(value, str):
            value = value.strip()
        return value not in ReconciliationService.BLACKLIST

    @staticmethod
    def rule_key(values, fields):
        key = []
        for name in fields:
            value = values[name].strip()
            key.append(value.casefold() if name == "name" else value)
        return tuple(key)

    # ---- values ----

    def import_values(self, definitions):
        """Copy the values of the matched machines, batch by batch (FR-006 to FR-009)"""
        machines = self.match_machines()
        LOGGER.info(f"Machines: {dict(self.result.machines)}")

        configs = AccountinfoConfig.objects.filter(datatarget="ASSET")
        blank = {str(config.id): self.empty(config.datatype) for config in configs}

        batches = [
            machines[start : start + self.batch_size]
            for start in range(0, len(machines), self.batch_size)
        ]
        for number, batch in enumerate(batches, start=1):
            self.progress(f"Batch {number}/{len(batches)}: {len(batch)} machines")
            rows, counts = [], Counter()
            try:
                with transaction.atomic():
                    self.import_batch(batch, definitions, blank, rows, counts)
            except Exception as e:
                if self.dry_run:
                    raise
                LOGGER.error(f"Batch {number} failed: {e}", exc_info=True)
                self.result.failed_batch = number
                self.result.error = str(e)
                self.report.writerow(
                    self.line("batch", status="failed", reason=f"batch {number}: {e}")
                )
                return

            # a batch reaches the report and the totals once committed
            for row in rows:
                self.report.writerow(row)
            self.result.values.update(counts)

    def import_batch(self, batch, definitions, blank, rows, counts):
        legacy = {
            row["HARDWARE_ID"]: row
            for row in self.legacy.accountinfo([m.hardware_id for m in batch])
        }
        stored = {
            data.object_id: data
            for data in AccountinfoData.objects.filter(
                content_type=self.content_type,
                object_id__in=[machine.asset_id for machine in batch],
            )
        }

        created, changed = [], []
        for machine in batch:
            values = legacy.get(machine.hardware_id)
            if values is None:
                continue

            data = stored.get(machine.asset_id)
            if data is None:
                data = AccountinfoData(
                    content_type=self.content_type,
                    object_id=machine.asset_id,
                    object_slug=ASSET_SLUG,
                    accountdata=dict(blank),
                )
                created.append(data)
            elif not isinstance(data.accountdata, dict):
                data.accountdata = dict(blank)

            touched = False
            for definition in definitions:
                status = self.import_value(machine, definition, values, data, rows)
                if status:
                    counts[status] += 1
                    touched = touched or status in ("imported", "overwritten")
            if touched and data.pk:
                changed.append(data)

        AccountinfoData.objects.bulk_create(created)
        AccountinfoData.objects.bulk_update(changed, ["accountdata"])

    def import_value(self, machine, definition, values, data, rows):
        raw = values.get(definition.column)
        if self.is_blank(raw):
            # an empty legacy value never clears a 3.x one
            return None

        key = str(definition.config.id)
        before = data.accountdata.get(key)
        row = self.line(
            "value",
            machine=machine,
            field=definition.name,
            legacy_value=self.text(raw),
            v3_value_before=self.text(before),
        )

        try:
            value = self.convert(definition, raw)
        except Rejected as e:
            rows.append({**row, "status": "rejected", "reason": str(e)})
            return "rejected"

        if before == value:
            status, reason = "kept", "already set to this value"
        elif self.is_empty(before):
            status, reason = "imported", ""
        elif self.overwrite:
            status, reason = "overwritten", ""
        else:
            status, reason = "kept", "3.x value already set"

        if status in ("imported", "overwritten"):
            data.accountdata[key] = value
        rows.append({**row, "status": status, "reason": reason})
        return status

    def convert(self, definition, raw):
        """The legacy value in the shape the 3.x config stores"""
        datatype = definition.config.datatype

        if not definition.is_list:
            if datatype not in TEXT_TYPES:
                raise Rejected(f"text value for a {datatype} config")
            if isinstance(raw, (datetime.date, datetime.datetime)):
                return raw.isoformat()[:10]
            return str(raw).strip() if definition.legacy_type == TEXT else str(raw)

        if datatype not in LIST_TYPES:
            raise Rejected(f"list value for a {datatype} config")

        if definition.legacy_type == CHECKBOX:
            picked = self.checkbox_values(definition, str(raw))
        else:
            index = self.as_int(str(raw).strip())
            if index not in definition.values:
                raise Rejected(f"unknown list index {raw}")
            picked = [definition.values[index]]

        if datatype == "CHECKBOX":
            return [value.id for value in picked]
        if len(picked) != 1:
            raise Rejected(f"{len(picked)} values for a SELECT config")
        return {"text": picked[0].value, "value": picked[0].id}

    def checkbox_values(self, definition, raw):
        """
        ocsreports stores the checked labels cut at their first space, each
        followed by &&& : 'value 1' and 'value 2' both become 'value'.
        """
        labels = list(definition.values.values())
        picked = []
        for token in raw.split(CHECKBOX_SEPARATOR):
            token = token.strip()
            if not token:
                continue

            exact = [v for v in labels if self.fold(v.value) == self.fold(token)]
            candidates = exact or [
                v
                for v in labels
                if self.fold(v.value).startswith(self.fold(token) + " ")
            ]
            if len(candidates) != 1:
                raise Rejected(f"ambiguous checkbox label '{token}'")
            if candidates[0] not in picked:
                picked.append(candidates[0])
        return picked

    # ---- helpers ----

    def definition_row(self, name, status, reason):
        self.report.writerow(
            self.line("definition", field=name, status=status, reason=reason)
        )

    def machine_row(self, machine):
        self.report.writerow(
            self.line(
                "machine", machine=machine, status=machine.status, reason=machine.reason
            )
        )

    @staticmethod
    def line(scope, machine=None, **values):
        row = dict.fromkeys(REPORT_COLUMNS, "")
        row["scope"] = scope
        if machine is not None:
            row["legacy_hardware_id"] = machine.hardware_id
            row["legacy_name"] = machine.name or ""
            row["deviceid"] = machine.deviceid or ""
            row["asset_id"] = machine.asset_id or ""
            row["match_rule"] = machine.rule
        row.update(values)
        return row

    @staticmethod
    def empty(datatype):
        if datatype == "CHECKBOX":
            return []
        if datatype == "SELECT":
            return None
        return ""

    @staticmethod
    def is_empty(value):
        return value in (None, "", [], {})

    @staticmethod
    def is_blank(raw):
        return raw is None or (isinstance(raw, str) and not raw.strip())

    @staticmethod
    def fold(text):
        return (text or "").strip().casefold()

    @staticmethod
    def text(value):
        if value is None:
            return ""
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()
        return str(value)

    @staticmethod
    def as_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def as_date(value):
        """LASTDATE comes as a datetime from MySQL, as text from sqlite"""
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.datetime.min
