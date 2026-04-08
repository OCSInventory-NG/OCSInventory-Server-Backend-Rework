from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from user.models import UserGroupAssignment


def _normalize_group_ids(group_ids):
    """Normalize incoming values into set of int group ids"""
    normalized_ids = set()
    for value in group_ids or []:
        if value is None:
            continue
        if isinstance(value, Group):
            normalized_ids.add(value.id)
            continue

        group_id = getattr(value, "id", value)
        try:
            normalized_ids.add(int(group_id))
        except (TypeError, ValueError):
            continue
    return normalized_ids


def _resolve_source_ref(source_object):
    """Resolve source object into content_type, object_id pair"""
    if source_object is None:
        return None, None

    if getattr(source_object, "pk", None) is None:
        raise ValueError("source_object must be a persisted instance")

    source_content_type = ContentType.objects.get_for_model(
        source_object, for_concrete_model=False
    )
    return source_content_type, source_object.pk


def sync_effective_groups(user):
    """Recompute and persist effective user.groups from all assignment sources"""
    effective_group_ids = (
        UserGroupAssignment.objects.filter(user=user)
        .values_list("group_id", flat=True)
        .distinct()
    )
    user.groups.set(effective_group_ids)


def sync_source_groups(
    user,
    source,
    group_ids,
    source_object=None,
):
    """
    Replace one source's group assignments for the user and recompute effective
    user.groups from all assignment sources
    """
    valid_sources = {choice[0] for choice in UserGroupAssignment.SOURCE_CHOICES}
    if source not in valid_sources:
        raise ValueError(f"Invalid source '{source}'")

    normalized_ids = _normalize_group_ids(group_ids)
    group_ids = set(
        Group.objects.filter(id__in=normalized_ids).values_list("id", flat=True)
    )
    source_content_type, source_object_id = _resolve_source_ref(source_object)

    with transaction.atomic():
        UserGroupAssignment.objects.filter(user=user, source=source).delete()

        assignments = [
            UserGroupAssignment(
                user=user,
                group_id=group_id,
                source=source,
                source_content_type=source_content_type,
                source_object_id=source_object_id,
            )
            for group_id in sorted(group_ids)
        ]
        if assignments:
            UserGroupAssignment.objects.bulk_create(assignments)

        sync_effective_groups(user)

    return group_ids


def upsert_group_assignment(
    user,
    group_id,
    source,
    source_content_type=None,
    source_object_id=None,
):
    """Create or update one assignment row then recompute effective groups"""
    valid_sources = {choice[0] for choice in UserGroupAssignment.SOURCE_CHOICES}
    if source not in valid_sources:
        raise ValueError(f"Invalid source '{source}'")

    if not Group.objects.filter(id=group_id).exists():
        raise ValueError(f"Unknown group '{group_id}'")

    if source == "manual":
        source_content_type = None
        source_object_id = None

    with transaction.atomic():
        assignment, created = UserGroupAssignment.objects.get_or_create(
            user=user,
            group_id=group_id,
            source=source,
            defaults={
                "source_content_type": source_content_type,
                "source_object_id": source_object_id,
            },
        )

        if not created and (
            assignment.source_content_type_id != getattr(source_content_type, "id", None)
            or assignment.source_object_id != source_object_id
        ):
            assignment.source_content_type = source_content_type
            assignment.source_object_id = source_object_id
            assignment.save(update_fields=["source_content_type", "source_object_id"])

        sync_effective_groups(user)

    return assignment


def delete_group_assignment(user, assignment_id):
    """Delete one assignment row for user then recompute effective groups"""
    with transaction.atomic():
        deleted_count, _ = UserGroupAssignment.objects.filter(
            id=assignment_id,
            user=user,
        ).delete()

        if deleted_count:
            sync_effective_groups(user)

    return deleted_count
