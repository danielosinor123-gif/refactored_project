"""File validation utilities: existence, size, extension, and hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Tuple

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class FileValidator:
    """Validates files before processing and computes content hashes."""

    def __init__(self, max_file_size_mb: float = 100.0, supported_extensions: Tuple[str, ...] = (".csv", ".json")):
        """Create a validator.

        Args:
            max_file_size_mb: Maximum allowed file size in megabytes.
            supported_extensions: Allowed file extensions (lowercase).
        """
        self.max_file_size_mb = float(max_file_size_mb)
        self.supported_extensions = tuple(ext.lower() for ext in supported_extensions)

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
        """Check that a file is not empty and within the configured size limit.

        Args:
            file_path: Path to the file to check.

        Returns:
            ``True`` when the size is acceptable, otherwise ``False``.
        """
        path = Path(file_path)
        if not path.exists():
            return False
        size_bytes = path.stat().st_size
        if size_bytes == 0:
            logger.warning("File is empty: %s", path)
            return False
        size_mb = size_bytes / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            logger.warning(
                "File exceeds size limit (%.2f MB > %.2f MB): %s",
                size_mb,
                self.max_file_size_mb,
                path,
            )
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
        extension = path.suffix.lower()
        if extension not in self.supported_extensions:
            logger.warning("Unsupported file extension '%s': %s", extension, path)
            return False
        return True

    def validate(self, file_path: str | Path) -> bool:
        """Run all validation checks against a file.

        Args:
            file_path: Path to the file to validate.

        Returns:
            ``True`` only when every check passes.
        """
        path = Path(file_path)
        return (
            self.validate_exists(path)
            and self.validate_extension(path)
            and self.validate_size(path)
        )

    def compute_hash(self, file_path: str | Path, algorithm: str = "sha256") -> str:
        """Compute the hash of a file's contents in a memory-efficient way.

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
                for chunk in iter(lambda: handle.read(65536), b""):
                    hasher.update(chunk)
        except OSError as exc:
            logger.error("Failed to hash file %s: %s", path, exc)
            return ""
        return hasher.hexdigest()

    def find_files(self, directory: str | Path) -> list:
        """List supported, non-empty files inside a directory.

        Args:
            directory: Directory to scan for files.

        Returns:
            Sorted list of :class:`~pathlib.Path` objects passing validation.
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.warning("Input directory does not exist or is not a directory: %s", directory)
            return []
        files = []
        for item in sorted(directory.iterdir()):
            if item.is_file() and self.validate(item):
                files.append(item)
        return files
