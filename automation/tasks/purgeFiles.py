import logging
from automation.tasks.abstractTask import AbstractTask
import os
from filemanager.models import FileManager
from django.conf import settings
import shutil
import uuid

logger = logging.getLogger("mgmt.management.commands.PurgeFiles")


class PurgeFiles(AbstractTask):
    """
    Automation task to purge orphaned files:
    - Deletes FileManager DB entries not linked to any deployment action
      (and their files)
    - Deletes uuid directories on disk that have no corresponding
      FileManager entry
    """

    def execute(self):
        """
        Purge orphaned files from both the database and the filesystem.
        """
        try:
            logger.info("Starting PurgeFiles task")

            # purge orphaned FileManager entries (not linked to any action)
            orphaned_files = FileManager.objects.filter(deployment_actions__isnull=True)
            count_orphaned_db = orphaned_files.count()
            if count_orphaned_db == 0:
                logger.warning("No orphaned FileManager entries found to purge.")
            else:
                logger.info(f"Found {count_orphaned_db} "
                            f"orphaned FileManager entries to purge.")
            for f in orphaned_files:
                logger.debug(
                    "Orphaned file: id=%s, name=%s, "
                    "path=%s, "
                    "created_at=%s",
                    f.id,
                    f.name,
                    f.file.name,
                    f.created_at,
                )
                try:
                    logger.debug(f"Purging orphaned file id={f.id}, name={f.name}")
                    f.delete()
                    logger.debug("Successfully purged orphaned file")
                except Exception as del_exc:
                    logger.error(
                        f"Failed to purge orphaned file id={f.id}: {del_exc}",
                        exc_info=True
                    )

            # purge orphaned uuid directories on disk (no DB entry)
            media_root = settings.MEDIA_ROOT
            logger.info("Scanning for orphaned file directories on disk...")
            count_orphaned_disk = 0
            for uuid_str, uuid_path in self.iter_uuid_dirs(media_root):
                try:
                    uuid_obj = uuid.UUID(uuid_str)
                except Exception as e:
                    logger.error(f"Error while iterating over media directories: {e}",
                                 exc_info=True)
                    continue
                if not FileManager.objects.filter(uuid=uuid_obj).exists():
                    try:
                        shutil.rmtree(uuid_path)
                        logger.debug(
                            "Purged orphaned file directory "
                            "(no DB entry): %s",
                            uuid_path,
                        )
                        count_orphaned_disk += 1
                    except Exception as e:
                        logger.error(
                            "Failed to purge orphaned file directory "
                            "%s: %s",
                            uuid_path,
                            e,
                        )
            if count_orphaned_disk == 0:
                logger.warning("No orphaned file directories found to purge on disk.")
            else:
                logger.info(f"Purged {count_orphaned_disk} "
                            f"orphaned file directories from disk.")

            logger.info("PurgeFiles task completed successfully.")
        except Exception as e:
            logger.error(f"Error in PurgeFiles task: {e}", exc_info=True)
            raise

    def iter_uuid_dirs(self, media_root):
        """
        Yield (uuid_str, uuid_path) for each candidate uuid directory under media_root
        """
        for model_dir in os.listdir(media_root):
            model_path = os.path.join(media_root, model_dir)
            if not os.path.isdir(model_path):
                continue
            for year in os.listdir(model_path):
                year_path = os.path.join(model_path, year)
                if not os.path.isdir(year_path):
                    continue
                for month in os.listdir(year_path):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path):
                        continue
                    for uuid_str in os.listdir(month_path):
                        uuid_path = os.path.join(month_path, uuid_str)
                        if not os.path.isdir(uuid_path):
                            continue
                        yield uuid_str, uuid_path
