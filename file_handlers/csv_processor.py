"""CSV file processing: validation, encoding detection, chunked loading."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from database.connection import DatabaseConnection
from utils.file_validator import FileValidator
from utils.logging_setup import get_logger

logger = get_logger(__name__)

_CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")


def detect_encoding(file_path: str | Path, sample_bytes: int = 65536) -> str:
    """Detect a readable text encoding for a CSV file.

    Args:
        file_path: Path to the CSV file.
        sample_bytes: Number of bytes to probe when testing encodings.

    Returns:
        The first encoding that decodes the sample cleanly, defaulting to
        ``utf-8`` when every candidate works or none can be probed.
    """
    path = Path(file_path)
    for encoding in _CANDIDATE_ENCODINGS:
        try:
            with path.open("r", encoding=encoding) as handle:
                handle.read(sample_bytes)
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError as exc:
            logger.error("Failed to read %s while detecting encoding: %s", path, exc)
            return "utf-8"
    return "latin-1"


def load_csv_file(
    file_path: str | Path,
    db: Optional[DatabaseConnection] = None,
    chunk_size: int = 1000,
) -> Optional[pd.DataFrame]:
    """Validate and load a CSV file into a DataFrame.

    Convenience wrapper around :class:`CSVProcessor`.

    Args:
        file_path: Path to the CSV file.
        db: Optional database connection used for raw-data load logging.
            When ``None``, the load is not logged to the database.
        chunk_size: Number of rows per chunk when loading large files.

    Returns:
        The combined :class:`pandas.DataFrame`, or ``None`` when the file
        fails validation or cannot be read.
    """
    validator = FileValidator(supported_extensions=(".csv",))
    if db is None:
        processor = CSVProcessor.__new__(CSVProcessor)
        processor.validator = validator
        processor.db = _NullDatabase()
        processor.chunk_size = int(chunk_size)
        return processor.load(file_path)
    processor = CSVProcessor(validator, db, chunk_size)
    return processor.load(file_path)


class _NullDatabase:
    """No-op stand-in for the database when load logging is disabled."""

    def insert_raw_data(self, source_file: str, file_hash: str, record_count: int) -> int:
        """Do nothing; return a dummy row id."""
        return 0


class CSVProcessor:
    """Loads and validates CSV files, logging each load to the database."""

    def __init__(self, validator: FileValidator, db: DatabaseConnection, chunk_size: int = 1000):
        """Create a CSV processor.

        Args:
            validator: File validator used before loading.
            db: Database connection used for raw-data load logging.
            chunk_size: Number of rows per chunk when loading large files.
        """
        self.validator = validator
        self.db = db
        self.chunk_size = int(chunk_size)

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
            Non-empty :class:`pandas.DataFrame` chunks.
        """
        reader = pd.read_csv(file_path, encoding=encoding, chunksize=self.chunk_size)
        for chunk in reader:
            if not chunk.empty:
                yield chunk

    def load(self, file_path: str | Path) -> Optional[pd.DataFrame]:
        """Validate and load a CSV file into a DataFrame.

        Args:
            file_path: Path to the CSV file.

        Returns:
            The combined :class:`pandas.DataFrame`, or ``None`` when the file
            fails validation or cannot be read.
        """
        path = Path(file_path)
        if not self.validator.validate(path):
            return None
        encoding = detect_encoding(path)
        file_hash = self.validator.compute_hash(path)
        chunks = []
        try:
            for chunk in self._iter_chunks(path, encoding):
                chunks.append(chunk)
        except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            logger.error("Failed to parse CSV file %s: %s", path, exc)
            return None

        if not chunks:
            logger.warning("No data rows found in CSV file: %s", path)
            return None

        frame = pd.concat(chunks, ignore_index=True)
        self.db.insert_raw_data(path.name, file_hash, len(frame))
        logger.info("Loaded %d rows from CSV %s (encoding=%s)", len(frame), path.name, encoding)
        return frame

    def load_api(self, base_url: str, api_key: str = "", timeout_seconds: int = 30) -> Optional[pd.DataFrame]:
        """Load CSV data from a remote API endpoint.

        Args:
            base_url: URL of the endpoint returning CSV content.
            api_key: Optional API key sent as a bearer token.
            timeout_seconds: Request timeout in seconds.

        Returns:
            The loaded :class:`pandas.DataFrame`, or ``None`` on failure.
        """
        try:
            import requests

            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = requests.get(base_url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - network layer raises many types
            logger.error("Failed to load CSV data from API %s: %s", base_url, exc)
            return None

        import io

        frame = pd.read_csv(io.StringIO(response.text))
        if frame.empty:
            logger.warning("API returned no data rows: %s", base_url)
            return None
        self.db.insert_raw_data("api:" + base_url, "", len(frame))
        logger.info("Loaded %d rows from API %s", len(frame), base_url)
        return frame
