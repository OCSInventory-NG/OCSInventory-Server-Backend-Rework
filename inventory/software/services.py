import logging
from typing import Dict, Iterable, List, Optional, Tuple

from asset.inventory_base.models import InventoryBase
from asset.inventory_section.models import InventorySection
from config.models import Config
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Now
from inventory.software.models import SoftwareDictionary, SoftwareMapping

logger = logging.getLogger(__name__)


class SoftwareDictionaryService:
    """Helper utilities to keep the SoftwareDictionary table in sync."""

    MODE_AUTOMATION = "automation"
    MODE_INVENTORY = "inventory"
    CONFIG_KEY = "software_dictionary_generation"

    @classmethod
    def rebuild(cls, asset_ids: Optional[Iterable[int]] = None) -> None:
        """
        Rebuild the dictionary for all assets or for the provided subset.

        Args:
            asset_ids: Optional list/queryset of InventoryBase ids to refresh.
        """
        queryset = InventoryBase.objects.all().select_related("template")
        cleanup_existing = True

        if asset_ids is not None:
            queryset = queryset.filter(id__in=asset_ids)
            logger.info(
                "Rebuilding software dictionary for %s assets", queryset.count()
            )
        else:
            logger.info("Rebuilding software dictionary for all assets")
            SoftwareDictionary.objects.all().delete()
            cleanup_existing = False

        processed = 0
        for asset in queryset.iterator():
            try:
                cls.refresh_asset(asset, cleanup_existing=cleanup_existing)
                processed += 1
            except Exception:
                logger.exception(
                    "Failed to refresh software dictionary for asset %s", asset.id
                )
        logger.info(
            "Software dictionary rebuild completed (%s assets processed)", processed
        )

    @classmethod
    def refresh_asset(cls, asset: InventoryBase, cleanup_existing: bool = True) -> None:
        """
        Recompute software entries for a single asset.

        Args:
            asset: InventoryBase to analyze.
            cleanup_existing: Remove existing references for this asset first.
        """
        if asset is None:
            return

        asset_id = asset.id
        entries = cls._build_entries_for_asset(asset)

        new_entries = {cls._signature_from_dict(entry): entry for entry in entries}
        existing_entries = cls._get_existing_entries(asset)

        keys_to_add = set(new_entries.keys()) - set(existing_entries.keys())
        keys_to_remove = set(existing_entries.keys()) - set(new_entries.keys())

        with transaction.atomic():
            if keys_to_remove:
                cls._detach_asset_entries(
                    asset_id, [existing_entries[key].id for key in keys_to_remove]
                )

            if keys_to_add:
                cls._attach_asset_entries(
                    asset, [new_entries[key] for key in keys_to_add]
                )

        logger.debug(
            "Asset %s software dictionary updated: %s extracted, %s added, %s removed",
            asset_id,
            len(entries),
            len(keys_to_add),
            len(keys_to_remove),
        )

    @classmethod
    def cleanup_delete(
        cls, asset_id: Optional[int], entry_ids: Optional[Iterable[int]]
    ) -> None:
        """Cleanup dictionary entries previously linked to a deleted asset"""
        if asset_id is None or entry_ids is None:
            return

        entry_ids_list = list(entry_ids)
        if not entry_ids_list:
            return

        cls._decrement_installation_numbers(entry_ids_list)
        cls._cleanup_empty_entries(entry_ids_list)

    @classmethod
    def _build_entries_for_asset(cls, asset: InventoryBase) -> List[Dict]:
        """Extract normalized software entries from an asset inventory."""
        if not asset.template_id:
            return []

        mappings = SoftwareMapping.objects.filter(template_id=asset.template_id)
        if not mappings:
            return []

        section_map = {mapping.section_id: mapping for mapping in mappings}
        sections = InventorySection.objects.filter(
            base=asset, template_section_id__in=section_map.keys()
        ).prefetch_related("fields")

        entries: List[Dict] = []
        for section in sections:
            mapping = section_map.get(section.template_section_id)
            if not mapping:
                continue

            value_map = {
                field.template_field_id: cls._clean_value(field.value)
                for field in section.fields.all()
            }

            version_value = cls._value_for_field(mapping.version_id, value_map)

            major = cls._value_for_field(mapping.major_version_id, value_map)
            minor = cls._value_for_field(mapping.minor_version_id, value_map)
            patch = cls._value_for_field(mapping.patch_version_id, value_map)

            if asset.template and asset.template.os == "LEG":
                if not (major and minor and patch) and version_value:
                    cleaned_version = cls._clean_value(version_value)

                    if cleaned_version:
                        major_int, minor_int, patch_int = cls._split_version_number(
                            cleaned_version
                        )
                        major = str(major_int) if major_int is not None else None
                        minor = str(minor_int) if minor_int is not None else None
                        patch = str(patch_int) if patch_int is not None else None

            major = cls._parse_version_component(major)
            minor = cls._parse_version_component(minor)
            patch = cls._parse_version_component(patch)

            entry = {
                "name": cls._value_for_field(mapping.name_id, value_map),
                "publisher": cls._value_for_field(mapping.publisher_id, value_map),
                "version": version_value,
                "major_version": major,
                "minor_version": minor,
                "patch_version": patch,
            }

            if not entry["name"]:
                # nothing useful extracted
                continue

            entries.append(entry)

        return entries

    @staticmethod
    def _value_for_field(field_id: Optional[int], value_map: Dict[int, Optional[str]]):
        if not field_id:
            return None
        return value_map.get(field_id)

    @staticmethod
    def _clean_value(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _parse_version_component(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None

        import re

        match = re.match(r"^\d+", str(value).strip())
        return int(match.group(0)) if match else None

    @staticmethod
    def _split_version_number(
        version: str,
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Extract major/minor/patch from a legacy version string.
        Returns None when a component does not exist.
        """

        if not version:
            return None, None, None

        import re

        match = re.match(r"^(\d+(?:\.\d+)*)", version)
        if not match:
            return None, None, None

        numeric_part = match.group(1)
        parts = numeric_part.split(".")

        major = int(parts[0]) if len(parts) > 0 else None
        minor = int(parts[1]) if len(parts) > 1 else None
        patch = int(parts[2]) if len(parts) > 2 else None

        return major, minor, patch

    @classmethod
    def _get_existing_entries(
        cls, asset: InventoryBase
    ) -> Dict[Tuple, SoftwareDictionary]:
        """Return a mapping of signature -> existing entry"""
        entries = asset.software_dictionary_entries.all().only(
            "id",
            "name",
            "publisher",
            "version",
            "major_version",
            "minor_version",
            "patch_version",
        )
        return {cls._signature_from_entry(entry): entry for entry in entries}

    @staticmethod
    def _signature_from_entry(entry: SoftwareDictionary) -> Tuple:
        return (
            entry.name,
            entry.publisher,
            entry.version,
            entry.major_version,
            entry.minor_version,
            entry.patch_version,
        )

    @staticmethod
    def _signature_from_dict(entry: Dict) -> Tuple:
        return (
            entry.get("name"),
            entry.get("publisher"),
            entry.get("version"),
            entry.get("major_version"),
            entry.get("minor_version"),
            entry.get("patch_version"),
        )

    @classmethod
    def _detach_asset_entries(cls, asset_id: int, entry_ids: List[int]) -> None:
        """Detach an asset from a subset of dictionary entries"""
        if not entry_ids:
            return

        through_model = SoftwareDictionary.assets.through
        link_qs = through_model.objects.filter(
            softwaredictionary_id__in=entry_ids,
            inventorybase_id=asset_id,
        )
        removed_entry_ids = list(
            link_qs.values_list("softwaredictionary_id", flat=True).distinct()
        )
        if not removed_entry_ids:
            return

        link_qs.delete()
        cls._decrement_installation_numbers(removed_entry_ids)
        cls._cleanup_empty_entries(removed_entry_ids)

    @classmethod
    def _attach_asset_entries(cls, asset: InventoryBase, entries: List[Dict]) -> None:
        """Attach an asset to the provided dictionary entries"""
        through_model = SoftwareDictionary.assets.through
        created_count = 0
        for entry in entries:
            obj, created = SoftwareDictionary.objects.get_or_create(**entry)
            if created:
                created_count += 1

            _, relation_created = through_model.objects.get_or_create(
                softwaredictionary_id=obj.id,
                inventorybase_id=asset.id,
            )
            if relation_created:
                cls._increment_installation_numbers([obj.id])
            else:
                SoftwareDictionary.objects.filter(id=obj.id).update(updated_at=Now())

        if entries:
            logger.debug(
                "Linked asset %s to %s dictionary entries (%s newly created)",
                asset.id,
                len(entries),
                created_count,
            )

    @classmethod
    def _increment_installation_numbers(cls, entry_ids: Iterable[int]) -> None:
        unique_ids = list(set(entry_ids))
        if not unique_ids:
            return
        SoftwareDictionary.objects.filter(id__in=unique_ids).update(
            installation_number=F("installation_number") + 1,
            updated_at=Now(),
        )

    @classmethod
    def _decrement_installation_numbers(cls, entry_ids: Iterable[int]) -> None:
        unique_ids = list(set(entry_ids))
        if not unique_ids:
            return
        SoftwareDictionary.objects.filter(
            id__in=unique_ids,
            installation_number__gt=0,
        ).update(
            installation_number=F("installation_number") - 1,
            updated_at=Now(),
        )

    @classmethod
    def _cleanup_empty_entries(cls, entry_ids: Iterable[int]) -> None:
        unique_ids = list(set(entry_ids))
        if not unique_ids:
            return
        SoftwareDictionary.objects.filter(
            id__in=unique_ids,
            assets__isnull=True,
        ).delete()

    @classmethod
    def get_generation_mode(cls) -> str:
        """Return the configured generation mode (inventory/automation)."""
        server_conf = (
            Config.objects.filter(name="server").values_list("value", flat=True).first()
        )
        if not server_conf:
            return cls.MODE_INVENTORY

        for item in server_conf:
            if item.get("name") == cls.CONFIG_KEY:
                value = str(item.get("value", "")).strip().lower()
                if value in (cls.MODE_AUTOMATION, cls.MODE_INVENTORY):
                    return value
                break

        return cls.MODE_INVENTORY

    @classmethod
    def should_refresh_on_inventory(cls) -> bool:
        return cls.get_generation_mode() == cls.MODE_INVENTORY

    @classmethod
    def should_refresh_on_automation(cls) -> bool:
        return cls.get_generation_mode() == cls.MODE_AUTOMATION

    @classmethod
    def refresh_legacy_asset(cls, asset_ids: Optional[Iterable[int]] = None):
        queryset = InventoryBase.objects.filter(template__os="LEG")
        if asset_ids:
            queryset = queryset.filter(id__in=asset_ids)

        for asset in queryset.iterator():
            cls.refresh_asset(asset)
