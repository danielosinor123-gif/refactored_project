"""JSON file processing: loading, validation, and DataFrame conversion."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from database.connection import DatabaseConnection
from file_handlers.csv_processor import validate_file
from utils.file_validator import calculate_file_hash
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class JSONProcessor:
    """Loads and validates JSON files, logging each load to the database."""

    def __init__(self, db: Optional[DatabaseConnection] = None,
                 max_file_size: int = 100 * 1024 * 1024):
        """Create a JSON processor.

        Args:
            db: Database connection used for raw-data load logging. When
                ``None``, loads are not logged.
            max_file_size: Maximum allowed file size in bytes.
        """
        self.db = db
        self.max_file_size = int(max_file_size)

    def can_handle(self, file_path: str | Path) -> bool:
        """Check whether this processor handles the given file extension.

        Args:
            file_path: Path to the candidate file.

        Returns:
            ``True`` for ``.json`` files.
        """
        return Path(file_path).suffix.lower() == ".json"

    def to_dataframe(self, data) -> pd.DataFrame:
        """Convert loaded JSON data into a DataFrame.

        Args:
            data: Parsed JSON data (list of dicts, or a single dict).

        Returns:
            A :class:`pandas.DataFrame` built from the data.

        Raises:
            ValueError: When the JSON structure is unsupported.
        """
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return pd.DataFrame(data)
        if isinstance(data, dict):
            return pd.DataFrame([data])
        raise ValueError("Unsupported JSON structure")

    def load(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Validate and load a JSON file into a DataFrame.

        Args:
            file_path: Path to the JSON file.

        Returns:
            The loaded :class:`pandas.DataFrame`, or ``None`` on failure.
        """
        try:
            logger.info("Loading JSON file: %s", file_path)
            if not validate_file(file_path, self.max_file_size):
                return None

            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)

            df = self.to_dataframe(data)

            if self.db is not None:
                file_hash = calculate_file_hash(file_path)
                self.db.log_raw_load(
                    str(file_path), file_hash, len(df), os.path.getsize(file_path)
                )

            logger.info("Successfully loaded %d rows from JSON", len(df))
            return df
        except Exception as exc:  # noqa: BLE001 - load failures are logged
            logger.error("Failed to load JSON: %s", exc)
            return None


def load_json_file(
    file_path: str | Path,
    db: Optional[DatabaseConnection] = None,
    max_file_size: int = 100 * 1024 * 1024,
) -> Optional[pd.DataFrame]:
    """Validate and load a JSON file into a DataFrame.

    Convenience wrapper around :class:`JSONProcessor`.

    Args:
        file_path: Path to the JSON file.
        db: Optional database connection used for raw-data load logging.
        max_file_size: Maximum allowed file size in bytes.

    Returns:
        The loaded :class:`pandas.DataFrame`, or ``None`` on failure.
    """
    return JSONProcessor(db=db, max_file_size=max_file_size).load(file_path)
