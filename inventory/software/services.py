import logging
from typing import Dict, Iterable, List, Optional, Tuple

from asset.inventory_base.models import InventoryBase
from asset.inventory_section.models import InventorySection
from config.models import Config
from inventory.software.models import SoftwareDictionary, SoftwareMapping
from django.db import transaction
from django.db.models.functions import Now

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
        logger.info("Software dictionary rebuild completed (%s assets processed)", processed)

    @classmethod
    def refresh_asset(
        cls, asset: InventoryBase, cleanup_existing: bool = True
    ) -> None:
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

        new_entries = {
            cls._signature_from_dict(entry): entry
            for entry in entries
        }
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

            entry = {
                "name": cls._value_for_field(mapping.name_id, value_map),
                "publisher": cls._value_for_field(mapping.publisher_id, value_map),
                "version": cls._value_for_field(mapping.version_id, value_map),
                "major_version": cls._value_for_field(
                    mapping.major_version_id, value_map
                ),
                "minor_version": cls._value_for_field(
                    mapping.minor_version_id, value_map
                ),
                "patch_version": cls._value_for_field(
                    mapping.patch_version_id, value_map
                ),
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

    @classmethod
    def _get_existing_entries(
        cls, asset: InventoryBase
    ) -> Dict[Tuple, SoftwareDictionary]:
        """Return a mapping of signature -> existing entry"""
        entries = (
            asset.software_dictionary_entries.all()
            .only(
                "id",
                "name",
                "publisher",
                "version",
                "major_version",
                "minor_version",
                "patch_version",
            )
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
        through_model.objects.filter(
            softwaredictionary_id__in=entry_ids,
            inventorybase_id=asset_id,
        ).delete()

        empty_ids = list(
            SoftwareDictionary.objects.filter(
                id__in=entry_ids, assets__isnull=True
            ).values_list("id", flat=True)
        )
        remaining_ids = set(entry_ids) - set(empty_ids)

        if remaining_ids:
            SoftwareDictionary.objects.filter(id__in=remaining_ids).update(
                updated_at=Now()
            )

        if empty_ids:
            SoftwareDictionary.objects.filter(id__in=empty_ids).delete()

    @classmethod
    def _attach_asset_entries(cls, asset: InventoryBase, entries: List[Dict]) -> None:
        """Attach an asset to the provided dictionary entries"""
        created_count = 0
        for entry in entries:
            obj, created = SoftwareDictionary.objects.get_or_create(**entry)
            obj.assets.add(asset)
            if not created:
                SoftwareDictionary.objects.filter(id=obj.id).update(updated_at=Now())
            else:
                created_count += 1

        if entries:
            logger.debug(
                "Linked asset %s to %s dictionary entries (%s newly created)",
                asset.id,
                len(entries),
                created_count,
            )

    @classmethod
    def get_generation_mode(cls) -> str:
        """Return the configured generation mode (inventory/automation)."""
        server_conf = Config.objects.filter(name="server").values_list(
            "value", flat=True
        ).first()
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
