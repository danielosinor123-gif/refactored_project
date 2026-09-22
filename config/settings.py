"""Application configuration management.

Preserves the original configuration keys and defaults. Sensitive values
(email password, API key, encryption key) are never hardcoded: they are
read from environment variables. An optional INI file can override any
value via :func:`load_config_from_file`.
"""

from __future__ import annotations

import configparser
import os
from typing import Any, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "database_path": "data/analytics.db",
    "input_directory": "data/input/",
    "output_directory": "data/output/",
    "reports_directory": "reports/",
    "log_file": "logs/processor.log",
    "email_server": "smtp.gmail.com",
    "email_port": 587,
    "email_user": "analytics@company.com",
    # Sensitive: read from environment variables, never hardcoded.
    "email_password": os.getenv("DATA_PROCESSOR_EMAIL_PASSWORD", ""),
    "api_base_url": "https://api.dataservice.com/v1",
    "api_key": os.getenv("DATA_PROCESSOR_API_KEY", ""),
    "chunk_size": 10000,
    "max_file_size": 100 * 1024 * 1024,  # 100MB
    "backup_enabled": True,
    "encryption_key": os.getenv("DATA_PROCESSOR_ENCRYPTION_KEY", ""),
}


def _coerce(value: str) -> Any:
    """Convert a string INI value to bool, int, or float when appropriate.

    Args:
        value: Raw string value from the INI file.

    Returns:
        The coerced Python value.
    """
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if value.isdigit():
        return int(value)
    if value.replace(".", "").isdigit():
        return float(value)
    return value


def get_config() -> Dict[str, Any]:
    """Return the default configuration dictionary.

    Returns:
        A copy of the default configuration with sensitive values sourced
        from environment variables.
    """
    config = dict(DEFAULT_CONFIG)
    config["email_password"] = os.getenv("DATA_PROCESSOR_EMAIL_PASSWORD", "")
    config["api_key"] = os.getenv("DATA_PROCESSOR_API_KEY", "")
    config["encryption_key"] = os.getenv("DATA_PROCESSOR_ENCRYPTION_KEY", "")
    return config


def load_config_from_file(config: Dict[str, Any], config_file: str) -> Dict[str, Any]:
    """Load configuration overrides from an INI file into a config dict.

    Preserves the original behavior: iterates all INI sections and keys,
    coercing values to bool/int/float when appropriate. Unknown keys are
    still accepted and added to the configuration.

    Args:
        config: The configuration dictionary to update.
        config_file: Path to the INI configuration file.

    Returns:
        The updated configuration dictionary. On failure the original
        configuration is returned unchanged.
    """
    try:
        parser = configparser.ConfigParser()
        parser.read(config_file)
        for section in parser.sections():
            for key, value in parser.items(section):
                config[key] = _coerce(value)
        return config
    except Exception as exc:  # noqa: BLE001 - config failures are logged
        from utils.logging_setup import get_logger

        logger = get_logger(__name__)
        logger.error("Failed to load config: %s", exc)
        return config


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Build the application configuration, optionally from an INI file.

    Args:
        config_file: Optional path to an INI configuration file.

    Returns:
        The configuration dictionary.
    """
    config = get_config()
    if config_file:
        return load_config_from_file(config, config_file)
    return config


def get_default_ini_template() -> str:
    """Return an INI template documenting every supported configuration key."""
    return """[paths]
database_path = data/analytics.db
input_directory = data/input/
output_directory = data/output/
reports_directory = reports/
log_file = logs/processor.log

[email]
email_server = smtp.gmail.com
email_port = 587
email_user = analytics@company.com

[api]
api_base_url = https://api.dataservice.com/v1

[processing]
chunk_size = 10000
max_file_size = 104857600
backup_enabled = true

; Sensitive values are read from environment variables:
;   DATA_PROCESSOR_EMAIL_PASSWORD
;   DATA_PROCESSOR_API_KEY
;   DATA_PROCESSOR_ENCRYPTION_KEY
"""
