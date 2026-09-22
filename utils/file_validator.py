"""File validation and hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Tuple

from utils.logging_setup import get_logger

logger = get_logger(__name__)


def calculate_file_hash(file_path: str | Path, algorithm: str = "md5") -> str:
    """Calculate the hash of a file's contents in chunks.

    Preserves the original behavior: MD5 by default, read in 4096-byte
    chunks, returning ``None``-like empty string on failure.

    Args:
        file_path: Path to the file to hash.
        algorithm: Hash algorithm name supported by :mod:`hashlib`.

    Returns:
        Hex digest string, or an empty string when hashing fails.
    """
    path = Path(file_path)
    hasher = hashlib.new(algorithm)
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as exc:  # noqa: BLE001 - hash failures are logged
        logger.error("Hash calculation failed: %s", exc)
        return ""


class FileValidator:
    """Validates files before processing and computes content hashes."""

    def __init__(self, max_file_size: int = 100 * 1024 * 1024,
                 valid_extensions: Tuple[str, ...] = (".csv", ".json", ".xlsx", ".txt")):
        """Create a validator.

        Args:
            max_file_size: Maximum allowed file size in bytes.
            valid_extensions: Allowed file extensions.
        """
        self.max_file_size = int(max_file_size)
        self.valid_extensions = tuple(ext.lower() for ext in valid_extensions)

    def validate_exists(self, file_path: str | Path) -> bool:
        """Check that a file exists and is a regular file.

        Args:
            file_path: Path to the file to check.

        Returns:
            ``True`` when the file exists, otherwise ``False``.
        """
        path = Path(file_path)
        if not path.is_file():
            logger.warning("File does not exist or is not a file: %s", path)
            return False
        return True

    def validate_size(self, file_path: str | Path) -> bool:
        """Check that a file is not empty and within the size limit.

        Args:
            file_path: Path to the file to check.

        Returns:
            ``True`` when the size is acceptable, otherwise ``False``.
        """
        path = Path(file_path)
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == 0:
            logger.warning("File is empty: %s", path)
            return False
        if size > self.max_file_size:
            logger.warning("File too large (%d bytes): %s", size, path)
            return False
        return True

    def validate_extension(self, file_path: str | Path) -> bool:
        """Check that a file has a supported extension.

        Args:
            file_path: Path to the file to check.

        Returns:
            ``True`` when the extension is supported, otherwise ``False``.
        """
        path = Path(file_path)
        if not any(str(path).lower().endswith(ext) for ext in self.valid_extensions):
            logger.warning("Unsupported file type: %s", path)
            return False
        return True

    def validate(self, file_path: str | Path) -> bool:
        """Run all validation checks against a file.

        Args:
            file_path: Path to the file to validate.

        Returns:
            ``True`` only when every check passes.
        """
        return (
            self.validate_exists(file_path)
            and self.validate_extension(file_path)
            and self.validate_size(file_path)
        )

    def compute_hash(self, file_path: str | Path, algorithm: str = "md5") -> str:
        """Compute the hash of a file's contents.

        Args:
            file_path: Path to the file to hash.
            algorithm: Hash algorithm name supported by :mod:`hashlib`.

        Returns:
            Hex digest string, or an empty string when hashing fails.
        """
        return calculate_file_hash(file_path, algorithm)
