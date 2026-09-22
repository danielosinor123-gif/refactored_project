"""Application configuration management.

Default values are defined here. Values may be overridden by an optional INI
file and environment variables always take precedence for sensitive settings
(passwords, API keys, encryption keys). No real secrets are hardcoded.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG_FILENAME = "config.ini"


@dataclass
class AppConfig:
    """Typed application configuration used across the whole pipeline."""

    # Paths (relative paths are resolved against the project root).
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    database_path: Path = field(default_factory=lambda: Path("data") / "processed_data.db")
    input_directory: Path = field(default_factory=lambda: Path("data") / "input")
    output_directory: Path = field(default_factory=lambda: Path("data") / "output")
    report_directory: Path = field(default_factory=lambda: Path("reports") / "generated")
    backup_directory: Path = field(default_factory=lambda: Path("backups"))
    log_directory: Path = field(default_factory=lambda: Path("logs"))

    # Processing settings.
    chunk_size: int = 1000
    max_file_size_mb: float = 100.0
    supported_extensions: tuple = (".csv", ".json", ".xlsx", ".xls")

    # Logging settings.
    log_level: str = "INFO"
    log_file_name: str = "data_processor.log"

    # Email settings (password always via environment variable).
    email_enabled: bool = False
    smtp_server: str = "localhost"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    email_sender: str = "data-processor@example.com"
    email_recipients: list = field(default_factory=list)
    smtp_password: str = field(default_factory=lambda: os.getenv("DATA_PROCESSOR_SMTP_PASSWORD", ""))
    smtp_username: str = field(default_factory=lambda: os.getenv("DATA_PROCESSOR_SMTP_USERNAME", ""))

    # API settings (api key always via environment variable).
    api_enabled: bool = False
    api_base_url: str = "https://api.example.com/data"
    api_timeout_seconds: int = 30
    api_key: str = field(default_factory=lambda: os.getenv("DATA_PROCESSOR_API_KEY", ""))

    # Backup / cleanup settings.
    backup_enabled: bool = True
    backup_retention_days: int = 30
    cleanup_enabled: bool = True
    file_retention_days: int = 90

    # Encryption-related settings (key always via environment variable).
    encryption_enabled: bool = False
    encryption_key: str = field(default_factory=lambda: os.getenv("DATA_PROCESSOR_ENCRYPTION_KEY", ""))

    def resolve_paths(self) -> None:
        """Resolve all configured relative paths against the project root."""
        for attr in (
            "database_path",
            "input_directory",
            "output_directory",
            "report_directory",
            "backup_directory",
            "log_directory",
        ):
            value = getattr(self, attr)
            if not value.is_absolute():
                setattr(self, attr, self.project_root / value)


def _coerce_bool(value: str, default: bool) -> bool:
    """Convert a string to a boolean, falling back to the default value."""
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_config(ini_path: Optional[str | Path] = None) -> AppConfig:
    """Load configuration from defaults, an optional INI file, and env vars.

    Args:
        ini_path: Optional path to an INI configuration file. When not given,
            ``config.ini`` is used if it exists next to the project root.

    Returns:
        A fully populated :class:`AppConfig` with paths resolved.
    """
    config = AppConfig()
    path = Path(ini_path) if ini_path else config.project_root / DEFAULT_CONFIG_FILENAME
    if ini_path is None and not path.exists():
        return _finalize(config)

    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path, encoding="utf-8")

    def get(section: str, option: str, default: Any) -> str:
        return parser.get(section, option, fallback=default)

    if parser.has_section("paths"):
        config.database_path = Path(get("paths", "database_path", str(config.database_path)))
        config.input_directory = Path(get("paths", "input_directory", str(config.input_directory)))
        config.output_directory = Path(get("paths", "output_directory", str(config.output_directory)))
        config.report_directory = Path(get("paths", "report_directory", str(config.report_directory)))
        config.backup_directory = Path(get("paths", "backup_directory", str(config.backup_directory)))
        config.log_directory = Path(get("paths", "log_directory", str(config.log_directory)))

    if parser.has_section("processing"):
        config.chunk_size = parser.getint("processing", "chunk_size", fallback=config.chunk_size)
        config.max_file_size_mb = parser.getfloat(
            "processing", "max_file_size_mb", fallback=config.max_file_size_mb
        )

    if parser.has_section("logging"):
        config.log_level = get("logging", "level", config.log_level).upper()
        config.log_file_name = get("logging", "file_name", config.log_file_name)

    if parser.has_section("email"):
        config.email_enabled = _coerce_bool(
            get("email", "enabled", str(config.email_enabled)), config.email_enabled
        )
        config.smtp_server = get("email", "smtp_server", config.smtp_server)
        config.smtp_port = parser.getint("email", "smtp_port", fallback=config.smtp_port)
        config.smtp_use_tls = _coerce_bool(
            get("email", "use_tls", str(config.smtp_use_tls)), config.smtp_use_tls
        )
        config.email_sender = get("email", "sender", config.email_sender)
        recipients = get("email", "recipients", "")
        config.email_recipients = [r.strip() for r in recipients.split(",") if r.strip()]

    if parser.has_section("api"):
        config.api_enabled = _coerce_bool(get("api", "enabled", str(config.api_enabled)), config.api_enabled)
        config.api_base_url = get("api", "base_url", config.api_base_url)
        config.api_timeout_seconds = parser.getint("api", "timeout_seconds", fallback=config.api_timeout_seconds)

    if parser.has_section("backup"):
        config.backup_enabled = _coerce_bool(
            get("backup", "enabled", str(config.backup_enabled)), config.backup_enabled
        )
        config.backup_retention_days = parser.getint(
            "backup", "retention_days", fallback=config.backup_retention_days
        )
        config.cleanup_enabled = _coerce_bool(
            get("backup", "cleanup_enabled", str(config.cleanup_enabled)), config.cleanup_enabled
        )
        config.file_retention_days = parser.getint(
            "backup", "file_retention_days", fallback=config.file_retention_days
        )

    return _finalize(config)


def load_config_from_file(ini_path: str | Path) -> AppConfig:
    """Load configuration explicitly from an INI file.

    Args:
        ini_path: Path to the INI configuration file.

    Returns:
        A fully populated :class:`AppConfig` with paths resolved.
    """
    return load_config(ini_path)


def _finalize(config: AppConfig) -> AppConfig:
    """Resolve paths and return the finalized configuration."""
    config.resolve_paths()
    return config


def get_default_ini_template() -> str:
    """Return an INI template documenting every supported configuration key."""
    return """[paths]
database_path = data/processed_data.db
input_directory = data/input
output_directory = data/output
report_directory = reports/generated
backup_directory = backups
log_directory = logs

[processing]
chunk_size = 1000
max_file_size_mb = 100.0

[logging]
level = INFO
file_name = data_processor.log

[email]
enabled = false
smtp_server = localhost
smtp_port = 587
use_tls = true
sender = data-processor@example.com
recipients =

[api]
enabled = false
base_url = https://api.example.com/data
timeout_seconds = 30

[backup]
enabled = true
retention_days = 30
cleanup_enabled = true
file_retention_days = 90

; Sensitive values are read from environment variables:
;   DATA_PROCESSOR_SMTP_USERNAME, DATA_PROCESSOR_SMTP_PASSWORD
;   DATA_PROCESSOR_API_KEY
;   DATA_PROCESSOR_ENCRYPTION_KEY
"""
