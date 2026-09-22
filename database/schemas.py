"""SQL schema definitions and table-creation statements."""

from __future__ import annotations

import sqlite3
from typing import List

RAW_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    file_hash TEXT,
    loaded_at TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0
)
"""

PROCESSED_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    quality_score REAL,
    payload_json TEXT
)
"""

REPORTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    report_path TEXT,
    generated_at TEXT NOT NULL,
    summary TEXT
)
"""

AUDIT_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    event_detail TEXT,
    created_at TEXT NOT NULL
)
"""

ALL_SCHEMAS: List[str] = [
    RAW_DATA_SCHEMA,
    PROCESSED_DATA_SCHEMA,
    REPORTS_SCHEMA,
    AUDIT_LOG_SCHEMA,
]

TABLE_NAMES: List[str] = ["raw_data", "processed_data", "reports", "audit_log"]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all application tables if they do not already exist.

    Args:
        conn: An open SQLite connection used to execute the schema.
    """
    with conn:
        for schema in ALL_SCHEMAS:
            conn.execute(schema)


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check whether a table exists in the database.

    Args:
        conn: An open SQLite connection.
        table_name: Name of the table to look for.

    Returns:
        ``True`` when the table exists, otherwise ``False``.
    """
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None
