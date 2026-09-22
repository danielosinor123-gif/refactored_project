"""Database package: connection management and schema definitions."""

from database.connection import DatabaseConnection
from database.schemas import ALL_SCHEMAS, TABLE_NAMES, create_tables, table_exists

__all__ = [
    "DatabaseConnection",
    "ALL_SCHEMAS",
    "TABLE_NAMES",
    "create_tables",
    "table_exists",
]
