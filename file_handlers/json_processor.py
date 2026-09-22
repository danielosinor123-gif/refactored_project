"""JSON file processing: loading, validation, and DataFrame conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from database.connection import DatabaseConnection
from utils.file_validator import FileValidator
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class JSONProcessor:
    """Loads and validates JSON files, logging each load to the database."""

    def __init__(self, validator: FileValidator, db: DatabaseConnection):
        """Create a JSON processor.

        Args:
            validator: File validator used before loading.
            db: Database connection used for raw-data load logging.
        """
        self.validator = validator
        self.db = db

    def can_handle(self, file_path: str | Path) -> bool:
        """Check whether this processor handles the given file extension.

        Args:
            file_path: Path to the candidate file.

        Returns:
            ``True`` for ``.json`` files.
        """
        return Path(file_path).suffix.lower() == ".json"

    def validate_json(self, file_path: str | Path) -> bool:
        """Check that a file contains syntactically valid JSON.

        Args:
            file_path: Path to the JSON file.

        Returns:
            ``True`` when the file parses as JSON, otherwise ``False``.
        """
        path = Path(file_path)
        try:
            with path.open("r", encoding="utf-8") as handle:
                pd.read_json(handle)
            return True
        except (ValueError, UnicodeDecodeError) as exc:
            logger.error("Invalid JSON in file %s: %s", path, exc)
            return False
        except OSError as exc:
            logger.error("Failed to read JSON file %s: %s", path, exc)
            return False

    def load(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Validate and load a JSON file into a DataFrame.

        Args:
            file_path: Path to the JSON file.

        Returns:
            The loaded :class:`pandas.DataFrame`, or ``None`` when the file
            fails validation, is empty, or cannot be read.
        """
        path = Path(file_path)
        if not self.validator.validate(path):
            return None
        if not self.validate_json(path):
            return None

        file_hash = self.validator.compute_hash(path)
        try:
            frame = pd.read_json(path, encoding="utf-8")
        except (ValueError, OSError) as exc:
            logger.error("Failed to load JSON file %s: %s", path, exc)
            return None

        if frame.empty:
            logger.warning("No data rows found in JSON file: %s", path)
            return None

        self.db.insert_raw_data(path.name, file_hash, len(frame))
        logger.info("Loaded %d rows from JSON %s", len(frame), path.name)
        return frame

    def to_dataframe(self, records: list) -> pd.DataFrame:
        """Convert a list of dictionaries into a DataFrame.

        Args:
            records: List of dict-like records.

        Returns:
            A :class:`pandas.DataFrame` built from the records.
        """
        return pd.DataFrame.from_records(records)
