import csv
import io
import sqlite3
from unittest import mock

import pytest
from accountinfo.legacy_import import (
    REPORT_COLUMNS,
    LegacyAccountinfoImport,
    LegacyDatabase,
)
from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from asset.inventory_base.models import InventoryBase
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError

SLUG = "inventory_base.inventorybase"

# the ocsdb11 shape: TAG, a select (157), a checkbox (158), an SNMP TAG
SCHEMA = """
CREATE TABLE accountinfo_config (
    ID INTEGER, NAME_ACCOUNTINFO TEXT, TYPE INTEGER, NAME TEXT, ID_TAB INTEGER,
    COMMENT TEXT, SHOW_ORDER INTEGER, ACCOUNT_TYPE TEXT, DEFAULT_VALUE TEXT
);
CREATE TABLE accountinfo (
    HARDWARE_ID INTEGER, TAG TEXT, fields_157 TEXT, fields_158 TEXT,
    fields_159 TEXT, fields_160 TEXT
);
CREATE TABLE config (NAME TEXT, IVALUE INTEGER, TVALUE TEXT, COMMENTS TEXT);
CREATE TABLE hardware (ID INTEGER, DEVICEID TEXT, NAME TEXT, LASTDATE TEXT);
CREATE TABLE bios (HARDWARE_ID INTEGER, SSN TEXT);
CREATE TABLE snmp_accountinfo (SNMP_ID INTEGER, TAG TEXT);

INSERT INTO accountinfo_config VALUES
    (1, 'TAG', 0, 'TAG', 1, 'TAG', 1, 'COMPUTERS', NULL),
    (2, 'TAG', 0, 'TAG', 1, 'TAG', 1, 'SNMP', NULL),
    (157, NULL, 2, 'LOCATION', 1, 'Location', 2, 'COMPUTERS', ''),
    (158, NULL, 5, 'CHECKBOXEXAMPLE', 1, 'CHECKBOX EXAMPLE', 3, 'COMPUTERS', ''),
    (159, NULL, 14, 'PURCHASE', 1, 'Purchase date', 4, 'COMPUTERS', ''),
    (160, NULL, 7, 'PICTURE', 1, 'Picture', 5, 'COMPUTERS', ''),
    (161, NULL, 0, 'GONE', 1, 'Column dropped', 6, 'COMPUTERS', '');

INSERT INTO config VALUES
    ('GUI_VERSION', 0, '7067', NULL),
    ('ACCOUNT_VALUE_CHECKBOXEXAMPLE_1', 1, 'value 1', NULL),
    ('ACCOUNT_VALUE_CHECKBOXEXAMPLE_2', 2, 'value 2', NULL),
    ('ACCOUNT_VALUE_CHECKBOXEXAMPLE_3', 3, 'Spare', NULL),
    ('ACCOUNT_VALUE_LOCATION_1', 1, 'Paris', NULL),
    ('ACCOUNT_VALUE_LOCATION_2', 2, 'Marseille', NULL);

INSERT INTO snmp_accountinfo VALUES (1, 'SW-1'), (2, 'SW-2');
"""


@pytest.fixture
def legacy():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    database = LegacyDatabase(connection, label="ocsweb@legacy")
    yield database
    connection.close()


def add_machine(
    legacy, id, deviceid, name, serial="", lastdate="2026-01-01 00:00:00", **values
):
    db = legacy.connection
    db.execute(
        "INSERT INTO hardware VALUES (?, ?, ?, ?)", (id, deviceid, name, lastdate)
    )
    db.execute("INSERT INTO bios VALUES (?, ?)", (id, serial))
    db.execute(
        "INSERT INTO accountinfo VALUES (?, ?, ?, ?, ?, ?)",
        (
            id,
            values.get("tag"),
            values.get("location"),
            values.get("checkbox"),
            values.get("purchase"),
            values.get("picture"),
        ),
    )


def make_asset(uuid, name="PC", serial="S1"):
    return InventoryBase.objects.create(
        name=name, osname="os", uuid=uuid, serial=serial
    )


def accountdata(asset):
    return AccountinfoData.objects.get(
        content_type=ContentType.objects.get_for_model(InventoryBase),
        object_id=asset.id,
    ).accountdata


def config(name):
    return AccountinfoConfig.objects.get(name=name, datatarget="ASSET")


def run(legacy, **options):
    stream = io.StringIO()
    report = csv.DictWriter(stream, REPORT_COLUMNS, delimiter=";")
    result = LegacyAccountinfoImport(legacy, report, **options).run()
    rows = list(
        csv.DictReader(io.StringIO(stream.getvalue()), REPORT_COLUMNS, delimiter=";")
    )
    return result, rows


def statuses(rows, scope):
    return {(row["field"], row["status"]) for row in rows if row["scope"] == scope}


@pytest.mark.django_db
class TestDefinitions:
    def test_computers_fields_become_asset_configs(self, legacy):
        result, _ = run(legacy, definitions_only=True)

        assert config("TAG").datatype == "TEXT"
        assert config("LOCATION").datatype == "SELECT"
        assert config("LOCATION").description == "Location"
        assert config("CHECKBOXEXAMPLE").datatype == "CHECKBOX"
        assert config("PURCHASE").datatype == "TEXT"
        assert result.definitions["created"] == 4

    def test_unsupported_types_and_missing_columns_are_ignored(self, legacy):
        result, rows = run(legacy, definitions_only=True)

        assert ("PICTURE", "ignored") in statuses(rows, "definition")
        assert ("GONE", "ignored") in statuses(rows, "definition")
        assert not AccountinfoConfig.objects.filter(name__in=["PICTURE", "GONE"])
        assert result.definitions["ignored"] == 2
        assert "type 7" in result.ignored_reasons

    def test_snmp_fields_are_only_counted(self, legacy):
        result, _ = run(legacy, definitions_only=True)

        assert result.snmp_fields == 1
        assert result.snmp_devices == 2
        assert AccountinfoConfig.objects.filter(name="TAG").count() == 1

    def test_list_values_keep_the_legacy_order(self, legacy):
        run(legacy, definitions_only=True)

        values = config("LOCATION").accountinfo_values.order_by("id")
        assert [value.value for value in values] == ["Paris", "Marseille"]

    def test_an_existing_config_is_reused_and_its_values_completed(self, legacy):
        location = AccountinfoConfig.objects.create(
            name="LOCATION", description="kept", datatype="SELECT", datatarget="ASSET"
        )
        AccountinfoValue.objects.create(accountinfo_config=location, value="paris ")

        result, _ = run(legacy, definitions_only=True)

        location.refresh_from_db()
        assert location.description == "kept"
        assert result.definitions["existing"] == 1
        assert sorted(location.accountinfo_values.values_list("value", flat=True)) == [
            "Marseille",
            "paris ",
        ]

    def test_an_ipdiscover_config_does_not_hide_the_asset_one(self, legacy):
        AccountinfoConfig.objects.create(
            name="TAG", description="TAG", datatype="TEXT", datatarget="IPDISCOVER"
        )

        run(legacy, definitions_only=True)

        assert config("TAG").datatarget == "ASSET"


@pytest.mark.django_db
class TestMatching:
    def test_deviceid_first_then_name_and_serial(self, legacy):
        by_deviceid = make_asset("DEV-1", name="PC-1", serial="A")
        by_rules = make_asset("NEW-UUID", name="pc-2", serial="B")
        add_machine(legacy, 1, "DEV-1", "PC-1", serial="A", tag="T1")
        add_machine(legacy, 2, "OLD-2", "PC-2", serial="B", tag="T2")

        result, _ = run(legacy)

        assert accountdata(by_deviceid)[str(config("TAG").id)] == "T1"
        assert accountdata(by_rules)[str(config("TAG").id)] == "T2"
        assert result.machines["deviceid"] == 1
        assert result.machines["duplicate:name+serial"] == 1

    def test_a_blank_serial_falls_back_on_the_name(self, legacy):
        # a 2.X agent sent to the 3.x server, new DEVICEID, virtual machine
        asset = make_asset(
            "OCS-CAU-MYSQL-2026-10-29", name="OCS-CAU-MYSQL", serial="Empty"
        )
        add_machine(legacy, 1, "OCS-CAU-MYSQL-2026-08-06", "OCS-CAU-MYSQL", tag="T1")

        result, _ = run(legacy)

        assert accountdata(asset)[str(config("TAG").id)] == "T1"
        assert result.machines["duplicate:name"] == 1

    def test_a_blank_serial_never_matches_a_blank_serial(self, legacy):
        make_asset("U1", name="PC-1", serial="Empty")
        add_machine(legacy, 1, "DEV-1", "PC-2", serial="", tag="T1")

        result, rows = run(legacy)

        assert result.machines["unmatched"] == 1
        assert rows[-1]["reason"] == "no asset matches on name"

    def test_no_asset_or_no_usable_value_is_unmatched(self, legacy):
        make_asset("OTHER", name="PC-9", serial="Z")
        add_machine(legacy, 1, "DEV-1", "PC-1", serial="A", tag="T1")
        add_machine(legacy, 2, "DEV-2", "", serial="", tag="T2")

        result, rows = run(legacy)

        assert result.machines["unmatched"] == 2
        reasons = {row["reason"] for row in rows if row["status"] == "unmatched"}
        assert reasons == {
            "no asset matches on name+serial",
            "no usable value on name+serial",
        }

    def test_several_candidate_assets_is_a_duplicate(self, legacy):
        make_asset("U1", name="PC-1", serial="A")
        make_asset("U2", name="PC-1", serial="A")
        add_machine(legacy, 1, "DEV-1", "PC-1", serial="A", tag="T1")

        result, _ = run(legacy)

        assert result.machines["duplicate"] == 1
        assert result.values["imported"] == 0

    def test_a_shared_asset_goes_to_the_latest_machine(self, legacy):
        asset = make_asset("DEV-NEW", name="PC-1", serial="A")
        add_machine(
            legacy,
            1,
            "OLD",
            "PC-1",
            serial="A",
            lastdate="2025-01-01 00:00:00",
            tag="OLD",
        )
        add_machine(
            legacy,
            2,
            "DEV-NEW",
            "PC-1",
            serial="A",
            lastdate="2026-06-01 00:00:00",
            tag="NEW",
        )

        result, rows = run(legacy)

        assert accountdata(asset)[str(config("TAG").id)] == "NEW"
        assert result.machines["duplicate"] == 1
        loser = next(row for row in rows if row["status"] == "duplicate")
        assert loser["legacy_hardware_id"] == "1"

    def test_a_shared_asset_with_the_same_lastdate_goes_to_nobody(self, legacy):
        make_asset("U1", name="PC-1", serial="A")
        add_machine(legacy, 1, "OLD-1", "PC-1", serial="A", tag="A")
        add_machine(legacy, 2, "OLD-2", "PC-1", serial="A", tag="B")

        result, _ = run(legacy)

        assert result.machines["duplicate"] == 2

    def test_groups_are_not_machines(self, legacy):
        add_machine(legacy, 1, "_SYSTEMGROUP_", "group", tag="G")

        result, _ = run(legacy)

        assert sum(result.machines.values()) == 0


@pytest.mark.django_db
class TestValues:
    def test_every_type_is_converted(self, legacy):
        asset = make_asset("DEV-1")
        add_machine(
            legacy,
            1,
            "DEV-1",
            "PC",
            tag=" T1 ",
            location="2",
            checkbox="Spare&&&",
            purchase="2024-03-01",
        )

        run(legacy)

        data = accountdata(asset)
        marseille = config("LOCATION").accountinfo_values.get(value="Marseille")
        spare = config("CHECKBOXEXAMPLE").accountinfo_values.get(value="Spare")
        assert data[str(config("TAG").id)] == "T1"
        assert data[str(config("LOCATION").id)] == {
            "text": "Marseille",
            "value": marseille.id,
        }
        assert data[str(config("CHECKBOXEXAMPLE").id)] == [spare.id]
        assert data[str(config("PURCHASE").id)] == "2024-03-01"

    def test_a_new_entry_holds_every_asset_config(self, legacy):
        other = AccountinfoConfig.objects.create(
            name="Owner", description="Owner", datatype="TEXT", datatarget="ASSET"
        )
        asset = make_asset("DEV-1")
        add_machine(legacy, 1, "DEV-1", "PC", tag="T1")

        run(legacy)

        data = accountdata(asset)
        assert data[str(other.id)] == ""
        assert data[str(config("LOCATION").id)] is None
        assert data[str(config("CHECKBOXEXAMPLE").id)] == []

    def test_a_set_value_is_kept_unless_overwrite(self, legacy):
        run(legacy, definitions_only=True)
        asset = make_asset("DEV-1")
        tag = str(config("TAG").id)
        AccountinfoData.objects.create(
            accountdata={tag: "V3"},
            object_slug=SLUG,
            content_type=ContentType.objects.get_for_model(InventoryBase),
            object_id=asset.id,
        )
        add_machine(legacy, 1, "DEV-1", "PC", tag="LEGACY")

        result, _ = run(legacy)
        assert accountdata(asset)[tag] == "V3"
        assert result.values["kept"] == 1

        result, _ = run(legacy, overwrite=True)
        assert accountdata(asset)[tag] == "LEGACY"
        assert result.values["overwritten"] == 1

    def test_an_empty_legacy_value_never_clears(self, legacy):
        run(legacy, definitions_only=True)
        asset = make_asset("DEV-1")
        tag = str(config("TAG").id)
        AccountinfoData.objects.create(
            accountdata={tag: "V3"},
            object_slug=SLUG,
            content_type=ContentType.objects.get_for_model(InventoryBase),
            object_id=asset.id,
        )
        add_machine(legacy, 1, "DEV-1", "PC", tag="  ")

        run(legacy, overwrite=True)

        assert accountdata(asset)[tag] == "V3"

    def test_values_that_do_not_fit_are_rejected(self, legacy):
        asset = make_asset("DEV-1")
        add_machine(legacy, 1, "DEV-1", "PC", location="9", checkbox="value&&&value&&&")

        result, rows = run(legacy)

        rejected = {
            row["field"]: row["reason"] for row in rows if row["status"] == "rejected"
        }
        assert rejected == {
            "LOCATION": "unknown list index 9",
            "CHECKBOXEXAMPLE": "ambiguous checkbox label 'value'",
        }
        assert result.values["rejected"] == 2
        assert accountdata(asset)[str(config("LOCATION").id)] is None

    def test_a_cut_label_matching_one_value_is_accepted(self, legacy):
        legacy.connection.execute(
            "UPDATE config SET TVALUE = 'Spare part' "
            "WHERE NAME = 'ACCOUNT_VALUE_CHECKBOXEXAMPLE_3'"
        )
        asset = make_asset("DEV-1")
        add_machine(legacy, 1, "DEV-1", "PC", checkbox="Spare&&&")

        run(legacy)

        spare = config("CHECKBOXEXAMPLE").accountinfo_values.get(value="Spare part")
        assert accountdata(asset)[str(config("CHECKBOXEXAMPLE").id)] == [spare.id]

    def test_a_second_run_changes_nothing(self, legacy):
        make_asset("DEV-1")
        add_machine(legacy, 1, "DEV-1", "PC", tag="T1", location="1")
        run(legacy)

        result, _ = run(legacy)

        assert result.definitions["created"] == 0
        assert result.values["imported"] == 0
        assert AccountinfoValue.objects.filter(value="Paris").count() == 1


@pytest.mark.django_db
class TestTransactions:
    def test_a_dry_run_writes_nothing_and_reports_the_same(self, legacy):
        asset = make_asset("DEV-1")
        add_machine(legacy, 1, "DEV-1", "PC", tag="T1")

        dry, dry_rows = run(legacy, dry_run=True)

        assert not AccountinfoConfig.objects.exists()
        assert not AccountinfoData.objects.filter(object_id=asset.id).exists()

        real, real_rows = run(legacy)
        assert dry.values == real.values
        assert dry.definitions == real.definitions
        assert [row["status"] for row in dry_rows] == [
            row["status"] for row in real_rows
        ]

    def test_a_failed_batch_keeps_the_previous_ones(self, legacy):
        for id in (1, 2, 3):
            make_asset(f"DEV-{id}", name=f"PC-{id}")
            add_machine(legacy, id, f"DEV-{id}", f"PC-{id}", tag=f"T{id}")

        original = LegacyAccountinfoImport.import_batch

        def import_batch(self, batch, *args):
            original(self, batch, *args)
            if batch[0].hardware_id == 2:
                raise RuntimeError("boom")

        with mock.patch.object(LegacyAccountinfoImport, "import_batch", import_batch):
            result, rows = run(legacy, batch_size=1)

        assert result.failed_batch == 2
        assert AccountinfoData.objects.count() == 1
        assert rows[-1]["status"] == "failed"


@pytest.mark.django_db
class TestCommand:
    def call(self, legacy, tmp_path, *args):
        out = io.StringIO()
        with (
            mock.patch.object(LegacyDatabase, "from_url", return_value=legacy),
            mock.patch.object(legacy, "close"),
        ):
            call_command(
                "import_legacy_accountinfo",
                "--legacy-url",
                "mysql://ocs:s3cret@legacy:3306/ocsweb",
                "--report",
                str(tmp_path / "report.csv"),
                *args,
                stdout=out,
            )
        return out.getvalue()

    def test_the_summary(self, legacy, tmp_path):
        make_asset("DEV-1")
        add_machine(legacy, 1, "DEV-1", "PC", tag="T1")

        output = self.call(legacy, tmp_path, "--dry-run")

        assert output.splitlines() == [
            "Legacy database: ocsweb@legacy (schema 7067) - read only"
            " - DRY RUN, nothing written",
            "Definitions: 4 created, 0 existing, 2 ignored"
            " (column fields_161 missing from accountinfo, type 7)",
            "Machines: 1 matched (1 by DEVICEID, 0 by duplicate rules),"
            " 0 unmatched, 0 duplicates",
            "Values: 1 imported, 0 kept (existing), 0 rejected",
            "SNMP accountinfo: 1 fields, 2 devices - not migrated",
            f"Report: {tmp_path / 'report.csv'}",
        ]
        assert "s3cret" not in output
        assert "s3cret" not in (tmp_path / "report.csv").read_text()

    def test_a_report_is_never_replaced(self, legacy, tmp_path):
        (tmp_path / "report.csv").write_text("previous")

        output = self.call(legacy, tmp_path, "--definitions-only")

        assert (tmp_path / "report.csv").read_text() == "previous"
        assert f"Report: {tmp_path / 'report-1.csv'}" in output
        assert "Machines: skipped (--definitions-only)" in output

    def test_invalid_options(self, legacy):
        with pytest.raises(CommandError) as error:
            call_command(
                "import_legacy_accountinfo",
                "--legacy-url",
                "mysql://h/db",
                "--batch-size",
                "0",
            )
        assert error.value.returncode == 1

        with pytest.raises(CommandError) as error:
            call_command("import_legacy_accountinfo", "--legacy-url", "postgres://h/db")
        assert error.value.returncode == 1

    def test_an_unreachable_database(self):
        with pytest.raises(CommandError) as error:
            call_command(
                "import_legacy_accountinfo",
                "--legacy-url",
                "mysql://ocs:pw@127.0.0.1:1/ocsweb",
            )
        assert error.value.returncode == 2
        assert "pw" not in str(error.value)
