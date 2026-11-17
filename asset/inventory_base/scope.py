from asset.inventory_base.models import InventoryBase

_CACHE_ATTR = "_visible_asset_ids"


def visible_asset_ids(user):
    """Subquery of the machine ids the user may see, None when unrestricted"""
    # imported here, the group and asset apps import each other's models
    from group.models import GroupAssetScope

    if user.is_superuser or user.has_perm("inventory_base.view_all_assets"):
        return None
    scopes = GroupAssetScope.objects.filter(group__in=user.groups.all())
    if not scopes.exists():
        return None
    return (
        InventoryBase.objects.filter(assetgroup__scoped_user_groups__in=scopes)
        .values("pk")
        .distinct()
    )


def visible_asset_ids_for(request):
    """visible_asset_ids computed once per request"""
    if request is None:
        return None
    if not hasattr(request, _CACHE_ATTR):
        setattr(request, _CACHE_ATTR, visible_asset_ids(request.user))
    return getattr(request, _CACHE_ATTR)
