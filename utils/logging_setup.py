"""Logging configuration and logger creation utilities."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_configured = False


def setup_logging(
    log_directory: Optional[Path] = None,
    level: str = "INFO",
    log_file_name: str = "data_processor.log",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure the root logger with console and rotating file handlers.

    Args:
        log_directory: Directory for log files. When ``None``, only console
            logging is configured.
        level: Log level name (e.g. ``"INFO"``, ``"DEBUG"``).
        log_file_name: Name of the log file inside ``log_directory``.
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated log files to keep.

    Returns:
        The configured root logger.
    """
    global _configured
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_directory is not None:
        log_directory = Path(log_directory)
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_directory / log_file_name,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _configured = True
    return logging.getLogger("data_processor")


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, lazily configured with console output.

    Args:
        name: Logger name, usually ``__name__`` of the calling module.

    Returns:
        A :class:`logging.Logger` instance.
    """
    if not _configured:
        setup_logging(level="INFO")
    return logging.getLogger(name)
