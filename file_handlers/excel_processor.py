"""Excel file processing: loading and validation via pandas/openpyxl.

The original application accepted ``.xlsx`` in its valid extensions; this
module provides the corresponding input support.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from database.connection import DatabaseConnection
from file_handlers.csv_processor import validate_file
from utils.file_validator import calculate_file_hash
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class ExcelProcessor:
    """Loads and validates Excel files, logging each load to the database."""

    def __init__(self, db: Optional[DatabaseConnection] = None,
                 max_file_size: int = 100 * 1024 * 1024, sheet_name: str | int = 0):
        """Create an Excel processor.

        Args:
            db: Database connection used for raw-data load logging. When
                ``None``, loads are not logged.
            max_file_size: Maximum allowed file size in bytes.
            sheet_name: Sheet to read (index or name). Defaults to first sheet.
        """
        self.db = db
        self.max_file_size = int(max_file_size)
        self.sheet_name = sheet_name

    def can_handle(self, file_path: str | Path) -> bool:
        """Check whether this processor handles the given file extension.

        Args:
            file_path: Path to the candidate file.

        Returns:
            ``True`` for ``.xlsx`` and ``.xls`` files.
        """
        return Path(file_path).suffix.lower() in (".xlsx", ".xls")

    def load(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Validate and load an Excel file into a DataFrame.

        Args:
            file_path: Path to the Excel file.

        Returns:
            The loaded :class:`pandas.DataFrame`, or ``None`` on failure.
        """
        try:
            logger.info("Loading Excel file: %s", file_path)
            if not validate_file(file_path, self.max_file_size):
                return None
            frame = pd.read_excel(file_path, sheet_name=self.sheet_name)

            if self.db is not None:
                file_hash = calculate_file_hash(file_path)
                self.db.log_raw_load(
                    str(file_path), file_hash, len(frame), os.path.getsize(file_path)
                )

            logger.info("Successfully loaded %d rows from Excel", len(frame))
            return frame
        except Exception as exc:  # noqa: BLE001 - load failures are logged
            logger.error("Failed to load Excel: %s", exc)
            return None


def load_excel_file(
    file_path: str | Path,
    db: Optional[DatabaseConnection] = None,
    max_file_size: int = 100 * 1024 * 1024,
) -> Optional[pd.DataFrame]:
    """Validate and load an Excel file into a DataFrame.

    Convenience wrapper around :class:`ExcelProcessor`.

    Args:
        file_path: Path to the Excel file.
        db: Optional database connection used for raw-data load logging.
        max_file_size: Maximum allowed file size in bytes.

    Returns:
        The loaded :class:`pandas.DataFrame`, or ``None`` on failure.
    """
    return ExcelProcessor(db=db, max_file_size=max_file_size).load(file_path)
