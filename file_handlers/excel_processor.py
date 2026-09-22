"""Excel file processing: loading and validation via pandas/openpyxl."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from database.connection import DatabaseConnection
from utils.file_validator import FileValidator
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class ExcelProcessor:
    """Loads and validates Excel files, logging each load to the database."""

    def __init__(self, validator: FileValidator, db: DatabaseConnection, sheet_name: str | int = 0):
        """Create an Excel processor.

        Args:
            validator: File validator used before loading.
            db: Database connection used for raw-data load logging.
            sheet_name: Sheet to read (index or name). Defaults to first sheet.
        """
        self.validator = validator
        self.db = db
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
            The loaded :class:`pandas.DataFrame`, or ``None`` when the file
            fails validation, is empty, or cannot be read.
        """
        path = Path(file_path)
        if not self.validator.validate(path):
            return None
        try:
            frame = pd.read_excel(path, sheet_name=self.sheet_name)
        except Exception as exc:  # noqa: BLE001 - openpyxl raises varied errors
            logger.error("Failed to load Excel file %s: %s", path, exc)
            return None

        if frame.empty:
            logger.warning("No data rows found in Excel file: %s", path)
            return None

        file_hash = self.validator.compute_hash(path)
        self.db.insert_raw_data(path.name, file_hash, len(frame))
        logger.info("Loaded %d rows from Excel %s", len(frame), path.name)
        return frame
