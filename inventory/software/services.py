import logging
from typing import Dict, Iterable, List, Optional

from asset.inventory_base.models import InventoryBase
from asset.inventory_section.models import InventorySection
from config.models import Config
from inventory.software.models import SoftwareDictionary, SoftwareMapping
from django.db import transaction

logger = logging.getLogger(__name__)


class SoftwareDictionaryService:
    """Helper utilities to keep the SoftwareDictionary table in sync."""

    MODE_AUTOMATION = "automation"
    MODE_COLLECTION = "collection"
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

        for asset in queryset.iterator():
            try:
                cls.refresh_asset(asset, cleanup_existing=cleanup_existing)
            except Exception:
                logger.exception(
                    "Failed to refresh software dictionary for asset %s", asset.id
                )

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

        with transaction.atomic():
            if cleanup_existing:
                cls._remove_asset_from_dictionary(asset_id)

            for entry in entries:
                cls._upsert_entry(entry, asset_id)

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
    def _remove_asset_from_dictionary(cls, asset_id: int) -> None:
        """Remove the asset id from every dictionary row."""
        entries = SoftwareDictionary.objects.filter(assets__contains=[asset_id])
        for entry in entries:
            assets = entry.assets or []
            assets = [item for item in assets if item != asset_id]
            if assets:
                entry.assets = assets
                entry.save(update_fields=["assets", "updated_at"])
            else:
                entry.delete()

    @classmethod
    def _upsert_entry(cls, entry: Dict, asset_id: int) -> None:
        obj, created = SoftwareDictionary.objects.get_or_create(
            **entry, defaults={"assets": [asset_id]}
        )
        if not created:
            assets = obj.assets or []
            if asset_id not in assets:
                assets.append(asset_id)
                obj.assets = assets
                obj.save(update_fields=["assets", "updated_at"])

    @classmethod
    def get_generation_mode(cls) -> str:
        """Return the configured generation mode (collection/automation)."""
        server_conf = Config.objects.filter(name="server").values_list(
            "value", flat=True
        ).first()
        if not server_conf:
            return cls.MODE_COLLECTION

        for item in server_conf:
            if item.get("name") == cls.CONFIG_KEY:
                value = str(item.get("value", "")).strip().lower()
                if value in (cls.MODE_AUTOMATION, cls.MODE_COLLECTION):
                    return value
                break

        return cls.MODE_COLLECTION

    @classmethod
    def should_refresh_on_collection(cls) -> bool:
        return cls.get_generation_mode() == cls.MODE_COLLECTION

    @classmethod
    def should_refresh_on_automation(cls) -> bool:
        return cls.get_generation_mode() == cls.MODE_AUTOMATION
