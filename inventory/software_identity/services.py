import logging
from collections import Counter

from django.db import transaction
from django.db.models import Q
from inventory.software.models import SoftwareDictionary
from inventory.software_identity.cpe.matcher import CpeMatcher
from inventory.software_identity.match_key import match_key
from inventory.software_identity.models import (
    IdentityDecision,
    PackageOrigin,
    SoftwareIdentity,
)
from inventory.software_identity.normalizers import build_normalizers
from inventory.software_identity.normalizers.base import (
    UNSUPPORTED,
    EffectiveDecision,
    IdentityResult,
    SoftwareRecord,
)

logger = logging.getLogger(__name__)

CPE_FAMILIES = ("windows", "macos")
LINUX_FAMILIES = ("deb", "rpm")


def _fit(field, value):
    """The value cut to the length of its SoftwareIdentity column."""
    return value[: SoftwareIdentity._meta.get_field(field).max_length]


class IdentityService:
    """Computes and stores the identity of software dictionary entries."""

    BATCH_SIZE = 500

    @classmethod
    def refresh(cls, batch_size=BATCH_SIZE):
        """
        Identify entries without identity, and Windows/macOS entries without a
        decision computed with an older CPE index. Without an index, only a
        catalog decision can identify a Windows/macOS entry: the others wait.
        """
        matcher = CpeMatcher()
        pending = cls._pending(matcher)
        counts = Counter()
        for start in range(0, len(pending), batch_size):
            # The catalog and the origins may change during a long run: read
            # them again per batch
            normalizers = build_normalizers(
                matcher, cls.effective_decisions(), cls.known_origins()
            )
            entries = (
                SoftwareDictionary.objects.filter(
                    id__in=pending[start : start + batch_size]
                )
                .select_related("identity")
                .order_by("name", "id")
            )
            for entry in entries:
                try:
                    with transaction.atomic():
                        result = cls._normalize(entry, normalizers, matcher)
                        if result is not None:
                            cls._save(entry, result, matcher.version)
                except Exception:
                    logger.exception(
                        "Identity failed for software dictionary entry %s", entry.id
                    )
                    counts["error"] += 1
                else:
                    counts["pending" if result is None else result.status] += 1
        return dict(counts)

    @classmethod
    @transaction.atomic
    def decide(cls, family, key, product, user):
        decision, _ = IdentityDecision.objects.update_or_create(
            family=family,
            match_key=key,
            source=IdentityDecision.SOURCE_ADMIN,
            defaults={"product": product, "user": user},
        )
        cls._recompute(family, key)
        return decision

    @classmethod
    @transaction.atomic
    def revert(cls, decision):
        if decision.source != IdentityDecision.SOURCE_ADMIN:
            raise ValueError("Shipped decisions cannot be deleted")
        family, key = decision.family, decision.match_key
        decision.delete()
        cls._recompute(family, key)

    @staticmethod
    def effective_decisions():
        """
        {(family, match_key): EffectiveDecision}, admin decisions over shipped ones.
        """
        decisions = {}
        for source in (IdentityDecision.SOURCE_SHIPPED, IdentityDecision.SOURCE_ADMIN):
            for decision in IdentityDecision.objects.filter(source=source):
                decisions[(decision.family, decision.match_key)] = EffectiveDecision(
                    decision.id, decision.product
                )
        return decisions

    @staticmethod
    def known_origins():
        """{origin name lowercased: distribution}, from PackageOrigin."""
        return {
            name.strip().lower(): distribution
            for name, distribution in PackageOrigin.objects.values_list(
                "name", "distribution"
            )
        }

    @staticmethod
    def reset_origins(names):
        """
        Linux entries of these origins go back to pending: the next refresh
        identifies them with the current PackageOrigin rows.
        """
        origins = {name.strip().lower() for name in names if name is not None}
        if not origins:
            return 0
        query = Q()
        for origin in origins:
            query |= Q(entry__package_origin__iexact=origin)
        deleted, _ = SoftwareIdentity.objects.filter(
            query, family__in=LINUX_FAMILIES
        ).delete()
        return deleted

    @staticmethod
    def _pending(matcher):
        """
        Ids to identify, ordered by name: the versions of a product follow each
        other and share the matcher cache.
        """
        pending = Q(identity__isnull=True)
        if matcher.available:
            pending |= Q(
                identity__family__in=CPE_FAMILIES,
                identity__decision__isnull=True,
                identity__index_version__lt=matcher.version,
            )
        return list(
            SoftwareDictionary.objects.filter(pending)
            .order_by("name", "id")
            .values_list("id", flat=True)
        )

    @staticmethod
    def _normalize(entry, normalizers, matcher):
        """IdentityResult of an entry, None while it waits for a CPE index."""
        family = entry.platform_family or ""
        if not family:
            return IdentityResult(UNSUPPORTED, "", reason="unknown_platform")
        normalizer = normalizers[family]
        if family in CPE_FAMILIES and not matcher.available:
            # Without an index only a catalog decision can identify the entry
            if (family, match_key(entry.name)) not in normalizer.decisions:
                return None
        record = SoftwareRecord(
            name=entry.name or "",
            publisher=entry.publisher or "",
            version=entry.version or "",
            architecture=entry.architecture or "",
            package_format=entry.package_format or "",
            source_package=entry.source_package or "",
            platform_family=family,
            platform_key=entry.platform_key or "",
            package_origin=entry.package_origin,
        )
        return normalizer.normalize(record)

    @staticmethod
    def _save(entry, result, index_version):
        family = entry.platform_family or ""
        values = {
            "family": family,
            "match_key": _fit("match_key", result.match_key),
            "status": result.status,
            "reason": result.reason,
            "scheme": result.scheme,
            "identifier": result.identifier,
            "product": _fit("product", result.product),
            "version": result.version,
            "score": result.score,
            "candidates": result.candidates,
            "decision_id": result.decision_id,
        }
        index_version = index_version if family in CPE_FAMILIES else 0
        identity = getattr(entry, "identity", None)
        if identity is not None and all(
            getattr(identity, name) == value for name, value in values.items()
        ):
            # Same result under a newer index: keep the row, only note the index
            if identity.index_version != index_version:
                SoftwareIdentity.objects.filter(pk=identity.pk).update(
                    index_version=index_version
                )
            return
        SoftwareIdentity.objects.update_or_create(
            entry=entry, defaults={**values, "index_version": index_version}
        )

    @classmethod
    def _recompute(cls, family, key):
        """
        Apply the current catalog to the identities of a product key, at once.
        Entries not identified yet get it at the next refresh.
        """
        matcher = CpeMatcher()
        normalizers = build_normalizers(matcher, cls.effective_decisions())
        identities = SoftwareIdentity.objects.filter(
            family=family, match_key=key
        ).select_related("entry")
        for identity in identities:
            result = cls._normalize(identity.entry, normalizers, matcher)
            if result is None:
                identity.delete()
            else:
                cls._save(identity.entry, result, matcher.version)
