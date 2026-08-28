import json
from pathlib import Path

from django.conf import settings
from django.db import transaction

from .models import Extension


def _iter_manifests():
    root = Path(settings.BASE_DIR) / "extensions"
    if not root.exists():
        return
    for ext_dir in root.iterdir():
        if not ext_dir.is_dir():
            continue
        manifest = ext_dir / "extension.json"
        if manifest.exists():
            yield manifest


@transaction.atomic
def sync_extensions_from_filesystem():
    for manifest_path in _iter_manifests():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        # the folder name is the reference: settings.py builds INSTALLED_APPS
        # from it, so it is the only value that cannot diverge
        django_app = manifest_path.parent.name
        defaults = {
            "name": data["name"],
            "description": data.get("description", ""),
            "version": data.get("version", "0.0.0"),
            "author": data.get("author", ""),
        }

        # matched on django_app, the unique column: 'name' is a display label
        # the author may change between versions, and two extensions may share
        # it, so it cannot identify a row
        obj, created = Extension.objects.get_or_create(
            django_app=django_app,
            defaults={**defaults, "enabled": False},
        )

        if not created:
            changed = False
            for k, v in defaults.items():
                if getattr(obj, k) != v:
                    setattr(obj, k, v)
                    changed = True
            if changed:
                obj.save(update_fields=list(defaults.keys()))
