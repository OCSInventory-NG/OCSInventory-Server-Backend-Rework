import logging

from automation.tasks.abstractTask import AbstractTask
from django.db import DatabaseError

logger = logging.getLogger("mgmt.management.commands.CveEnrichment")


class CveEnrichment(AbstractTask):
    """
    CveEnrichment task.

    Resolves a CPE for every software dictionary entry via cpe-guesser and,
    for confident matches, fetches associated CVEs from Vulnerability-Lookup.

    Never touches a CpeMatch that was decided by a human — REJECTED (any
    source) or CONFIRMED with source == manual. Those are frozen: neither
    the CPE nor its CVEs are ever re-fetched by this task.

    A CpeMatch that is CONFIRMED automatically (source == auto_guessed) is
    still passed to enrich_software() on every run: its CPE won't actually
    be re-guessed (enrich_software short-circuits on the CpeMatch TTL), but
    its CVE reports get refreshed once cache_validity_hours has elapsed —
    new CVEs published for an already-confirmed product must keep showing
    up, not freeze forever the moment the match is confirmed.
    """

    def execute(self):
        try:
            logger.info("Starting CveEnrichment task")
            from inventory.software.models import SoftwareDictionary
            from security.models import CpeMatch, CveReport

            softwares = SoftwareDictionary.objects.exclude(
                cpe_match__status=CpeMatch.STATUS_REJECTED
            ).exclude(
                cpe_match__status=CpeMatch.STATUS_CONFIRMED,
                cpe_match__source=CpeMatch.SOURCE_MANUAL,
            )

            total = softwares.count()
            logger.info("Found %d software entries to enrich", total)

            processed = 0
            failed = 0
            processed_software_ids = []

            for index, software in enumerate(softwares, 1):
                try:
                    logger.debug(
                        "Enriching software %d/%d: %s", index, total, software.name
                    )
                    self.enrich_software(software)
                    processed += 1
                    processed_software_ids.append(software.id)
                except Exception as e:
                    failed += 1
                    logger.error(
                        "Failed to enrich software %s: %s", software.name, e, exc_info=True
                    )

            matches = CpeMatch.objects.filter(software_id__in=processed_software_ids)
            confirmed = matches.filter(status=CpeMatch.STATUS_CONFIRMED).count()
            pending_review = matches.filter(status=CpeMatch.STATUS_PENDING_REVIEW).count()
            no_match = matches.filter(status=CpeMatch.STATUS_NO_MATCH).count()
            cve_count = CveReport.objects.filter(software_id__in=processed_software_ids).count()

            summary = (
                f"{processed}/{total} software processed ({failed} failed), "
                f"{cve_count} CVE(s) found, "
                f"CPE: {confirmed} reliable, {pending_review} to review, {no_match} no match"
            )

            logger.info("CveEnrichment task completed: %s", summary)
            return summary
        except Exception as e:
            logger.error("Critical error in CveEnrichment task: %s", e, exc_info=True)
            raise

    def enrich_software(self, software):
        try:
            from security.services import enrich_software

            enrich_software(software)
        except DatabaseError as e:
            logger.error(
                "Database error while enriching software %s: %s", software.name, e, exc_info=True
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error while enriching software %s: %s", software.name, e, exc_info=True
            )
            raise
