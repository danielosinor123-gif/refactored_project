"""File handlers for CSV, JSON, and Excel inputs."""

from pathlib import Path

from file_handlers.csv_processor import CSVProcessor, detect_encoding, load_csv_file
from file_handlers.excel_processor import ExcelProcessor
from file_handlers.json_processor import JSONProcessor, load_json_file
from utils.file_validator import FileValidator

_default_validator = FileValidator(supported_extensions=(".csv", ".json", ".xlsx", ".xls"))


def validate_file(file_path: str | Path) -> bool:
    """Validate a file before processing.

    Checks existence, supported extension, and size limits using a default
    validator configured for CSV, JSON, and Excel files.

    Args:
        file_path: Path to the file to validate.

    Returns:
        ``True`` only when every check passes.
    """
    return _default_validator.validate(file_path)


__all__ = [
    "CSVProcessor",
    "JSONProcessor",
    "ExcelProcessor",
    "detect_encoding",
    "load_csv_file",
    "load_json_file",
    "validate_file",
]
