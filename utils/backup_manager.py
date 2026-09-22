"""Backup and cleanup utilities for databases, outputs, and reports."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Optional

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class BackupManager:
    """Creates timestamped backups and removes files past the retention period."""

    def __init__(self, backup_directory: str | Path, retention_days: int = 30):
        """Create a backup manager.

        Args:
            backup_directory: Directory where backups are stored.
            retention_days: Number of days to retain backup artifacts.
        """
        self.backup_directory = Path(backup_directory)
        self.retention_days = int(retention_days)

    def _timestamped_target(self, category: str) -> Path:
        """Create and return a timestamped backup subdirectory for a category."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target = self.backup_directory / category / timestamp
        target.mkdir(parents=True, exist_ok=True)
        return target

    def backup_database(self, database_path: str | Path) -> Optional[Path]:
        """Back up the SQLite database file.

        Args:
            database_path: Path to the database file.

        Returns:
            Path of the backup copy, or ``None`` when the source is missing.
        """
        source = Path(database_path)
        if not source.is_file():
            logger.warning("Cannot back up missing database: %s", source)
            return None
        target = self._timestamped_target("database") / source.name
        shutil.copy2(source, target)
        logger.info("Database backed up to %s", target)
        return target

    def backup_directory_tree(self, source_directory: str | Path, category: str) -> Optional[Path]:
        """Back up an entire directory tree (e.g. output or reports).

        Args:
            source_directory: Directory to copy.
            category: Backup category subdirectory name.

        Returns:
            Path of the backup copy, or ``None`` when the source is missing.
        """
        source = Path(source_directory)
        if not source.is_dir():
            logger.warning("Cannot back up missing directory: %s", source)
            return None
        target = self._timestamped_target(category)
        shutil.copytree(source, target, dirs_exist_ok=True)
        logger.info("Directory backed up: %s -> %s", source, target)
        return target

    def backup_output(self, output_directory: str | Path) -> Optional[Path]:
        """Back up the processed-output directory.

        Args:
            output_directory: Directory containing generated output files.

        Returns:
            Path of the backup copy, or ``None`` when the source is missing.
        """
        return self.backup_directory_tree(output_directory, "output")

    def backup_reports(self, report_directory: str | Path) -> Optional[Path]:
        """Back up the generated-reports directory.

        Args:
            report_directory: Directory containing generated report files.

        Returns:
            Path of the backup copy, or ``None`` when the source is missing.
        """
        return self.backup_directory_tree(report_directory, "reports")

    def cleanup_old_files(self, directory: str | Path, retention_days: Optional[int] = None) -> int:
        """Delete files in a directory older than the retention period.

        Args:
            directory: Directory to clean up.
            retention_days: Optional override for the configured retention days.

        Returns:
            Number of files removed.
        """
        days = self.retention_days if retention_days is None else int(retention_days)
        directory = Path(directory)
        if not directory.is_dir():
            logger.warning("Cannot clean up missing directory: %s", directory)
            return 0
        cutoff = time.time() - days * 86400
        removed = 0
        for item in sorted(directory.rglob("*")):
            if item.is_file():
                try:
                    if item.stat().st_mtime < cutoff:
                        item.unlink()
                        removed += 1
                except OSError as exc:
                    logger.error("Failed to remove old file %s: %s", item, exc)
        if removed:
            logger.info("Removed %d file(s) older than %d day(s) from %s", removed, days, directory)
        else:
            logger.debug("No files older than %d day(s) in %s", days, directory)
        return removed
