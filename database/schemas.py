"""SQL schema definitions and table-creation statements.

Preserves the original table names and required database fields from the
monolithic application: raw_data, processed_data, reports, and audit_log.
"""

from __future__ import annotations

import sqlite3
from typing import List

RAW_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_hash TEXT NOT NULL,
    row_count INTEGER,
    file_size INTEGER,
    processing_status TEXT DEFAULT 'pending'
)
"""

PROCESSED_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_data_id INTEGER,
    processed_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    transformation_type TEXT,
    output_file TEXT,
    quality_score REAL,
    error_count INTEGER DEFAULT 0,
    FOREIGN KEY (raw_data_id) REFERENCES raw_data (id)
)
"""

REPORTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    generated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    recipient_email TEXT,
    status TEXT DEFAULT 'generated'
)
"""

AUDIT_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    user_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    ip_address TEXT
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
    cursor = conn.cursor()
    for schema in ALL_SCHEMAS:
        cursor.execute(schema)
    conn.commit()


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
