"""CSV file processing: validation, encoding detection, chunked loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pandas as pd

from database.connection import DatabaseConnection
from utils.file_validator import calculate_file_hash
from utils.logging_setup import get_logger

logger = get_logger(__name__)

_CANDIDATE_ENCODINGS = ("utf-8", "latin1", "cp1252")
_DEFAULT_EXTENSIONS: Tuple[str, ...] = (".csv", ".json", ".xlsx", ".txt")
DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024


def validate_file(
    file_path: str | Path,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    valid_extensions: Tuple[str, ...] = _DEFAULT_EXTENSIONS,
) -> bool:
    """Validate an input file: existence, size, and supported extension.

    Logs a warning and returns ``False`` on any failure, matching the
    original error-handling behavior.

    Args:
        file_path: Path to the file to validate.
        max_file_size: Maximum allowed file size in bytes.
        valid_extensions: Allowed file extensions.

    Returns:
        ``True`` when every check passes, otherwise ``False``.
    """
    path = Path(file_path)
    try:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        file_size = os.path.getsize(file_path)
        if file_size > max_file_size:
            raise ValueError(f"File too large: {file_size} bytes")
        if file_size == 0:
            raise ValueError("File is empty")
        if not any(str(file_path).lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(f"Unsupported file type: {file_path}")
        return True
    except Exception as exc:  # noqa: BLE001 - validation failures are logged
        logger.error("File validation failed: %s", exc)
        return False


class CSVProcessor:
    """Loads and validates CSV files, logging each load to the database."""

    def __init__(self, db: Optional[DatabaseConnection] = None, chunk_size: int = 10000,
                 max_file_size: int = DEFAULT_MAX_FILE_SIZE):
        """Create a CSV processor.

        Args:
            db: Database connection used for raw-data load logging. When
                ``None``, loads are not logged.
            chunk_size: Number of rows per chunk when loading large files.
            max_file_size: Maximum allowed file size in bytes.
        """
        self.db = db
        self.chunk_size = int(chunk_size)
        self.max_file_size = int(max_file_size)

    def can_handle(self, file_path: str | Path) -> bool:
        """Check whether this processor handles the given file extension.

        Args:
            file_path: Path to the candidate file.

        Returns:
            ``True`` for ``.csv`` files.
        """
        return Path(file_path).suffix.lower() == ".csv"

    def _iter_chunks(self, file_path: Path, encoding: str) -> Iterator[pd.DataFrame]:
        """Yield consecutive row chunks from a CSV file.

        Args:
            file_path: Path to the CSV file.
            encoding: Text encoding to use when reading.

        Yields:
            :class:`pandas.DataFrame` chunks.
        """
        reader = pd.read_csv(file_path, encoding=encoding, chunksize=self.chunk_size)
        for chunk in reader:
            yield chunk

    def load(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Validate and load a CSV file into a DataFrame.

        Args:
            file_path: Path to the CSV file.

        Returns:
            The combined :class:`pandas.DataFrame`, or ``None`` on failure.
        """
        try:
            logger.info("Loading CSV file: %s", file_path)
            if not validate_file(file_path, self.max_file_size):
                return None

            df = None
            for encoding in _CANDIDATE_ENCODINGS:
                try:
                    df = self._iter_chunks(Path(file_path), encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                raise ValueError("Could not decode file with any encoding")

            all_data = list(df)
            final_df = pd.concat(all_data, ignore_index=True)

            if self.db is not None:
                file_hash = calculate_file_hash(file_path)
                self.db.log_raw_load(
                    str(file_path), file_hash, len(final_df), os.path.getsize(file_path)
                )

            logger.info("Successfully loaded %d rows from %s", len(final_df), file_path)
            return final_df
        except Exception as exc:  # noqa: BLE001 - load failures are logged
            logger.error("Failed to load CSV: %s", exc)
            return None


def load_csv_file(
    file_path: str | Path,
    db: Optional[DatabaseConnection] = None,
    chunk_size: int = 10000,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> Optional[pd.DataFrame]:
    """Validate and load a CSV file into a DataFrame.

    Convenience wrapper around :class:`CSVProcessor`.

    Args:
        file_path: Path to the CSV file.
        db: Optional database connection used for raw-data load logging.
        chunk_size: Number of rows per chunk when loading large files.
        max_file_size: Maximum allowed file size in bytes.

    Returns:
        The combined :class:`pandas.DataFrame`, or ``None`` on failure.
    """
    return CSVProcessor(db=db, chunk_size=chunk_size, max_file_size=max_file_size).load(file_path)
