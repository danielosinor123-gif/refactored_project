"""Backup and cleanup utilities for databases, outputs, and reports."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class BackupManager:
    """Creates timestamped backups and removes files past the retention period."""

    def __init__(self, backup_root: str | Path = "backups", backup_enabled: bool = True):
        """Create a backup manager.

        Args:
            backup_root: Root directory for backups.
            backup_enabled: Whether backups are enabled.
        """
        self.backup_root = Path(backup_root)
        self.backup_enabled = bool(backup_enabled)

    def create_backup(self, database_path: str | Path, output_directory: Optional[str | Path] = None,
                      reports_directory: Optional[str | Path] = None) -> Optional[Path]:
        """Create a timestamped backup of the database, output, and reports.

        Preserves the original behavior: copies the database as
        ``database_backup.db``, copies the output and reports trees, and
        writes a ``backup_info.json`` metadata file.

        Args:
            database_path: Path to the SQLite database file.
            output_directory: Optional directory of generated output files.
            reports_directory: Optional directory of generated reports.

        Returns:
            Path of the created backup directory, or ``None`` on failure.
        """
        if not self.backup_enabled:
            return None
        try:
            logger.info("Creating data backup")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.backup_root / f"backup_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            shutil.copy2(database_path, backup_dir / "database_backup.db")

            if output_directory and os.path.exists(output_directory):
                shutil.copytree(output_directory, backup_dir / "output", dirs_exist_ok=True)
            if reports_directory and os.path.exists(reports_directory):
                shutil.copytree(reports_directory, backup_dir / "reports", dirs_exist_ok=True)

            files = os.listdir(backup_dir)
            backup_info = {
                "timestamp": timestamp,
                "database_size": os.path.getsize(database_path),
                "files_backed_up": len(files),
                "backup_size": sum(
                    os.path.getsize(os.path.join(backup_dir, f))
                    for f in files
                    if os.path.isfile(os.path.join(backup_dir, f))
                ),
            }
            with open(backup_dir / "backup_info.json", "w", encoding="utf-8") as handle:
                json.dump(backup_info, handle, indent=2)

            logger.info("Backup created: %s", backup_dir)
            return backup_dir
        except Exception as exc:  # noqa: BLE001 - backup failures are logged
            logger.error("Backup failed: %s", exc)
            return None

    def cleanup_old_files(self, days_old: int = 30, directories: Optional[list] = None) -> int:
        """Delete files older than the retention period.

        Preserves the original behavior: cleans the output and reports
        directories (or the directories provided).

        Args:
            days_old: Age threshold in days.
            directories: Optional explicit list of directories to clean.
                Defaults to the output and reports directories under the
                current working directory.

        Returns:
            Number of files removed.
        """
        try:
            logger.info("Cleaning up files older than %d days", days_old)
            if directories is None:
                directories = ["data/output/", "reports/"]
            cutoff_date = datetime.now() - timedelta(days=days_old)
            removed = 0
            for directory in directories:
                if not os.path.exists(directory):
                    continue
                for file_path in Path(directory).rglob("*"):
                    if file_path.is_file():
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_mtime < cutoff_date:
                            file_path.unlink()
                            logger.info("Deleted old file: %s", file_path)
                            removed += 1
            return removed
        except Exception as exc:  # noqa: BLE001 - cleanup failures are logged
            logger.error("Cleanup failed: %s", exc)
            return 0
