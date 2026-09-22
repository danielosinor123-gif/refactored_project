"""SQLite connection management and database initialization."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional

from database.schemas import create_tables, table_exists

_row_factory = sqlite3.Row


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


class DatabaseConnection:
    """Manages the lifecycle of a SQLite database connection.

    Row access uses :class:`sqlite3.Row` so rows behave like both mappings
    and sequences, matching the row-access style of the original code.
    """

    def __init__(self, database_path: str | Path):
        """Create a connection wrapper.

        Args:
            database_path: Path to the SQLite database file. Parent
                directories are created lazily on connect.
        """
        self.database_path = Path(database_path)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Open the database connection, creating the file if needed.

        Returns:
            The open :class:`sqlite3.Connection`.

        Raises:
            sqlite3.Error: When the connection cannot be established.
        """
        if self._conn is not None:
            return self._conn
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.database_path))
        self._conn.row_factory = _row_factory
        return self._conn

    def close(self) -> None:
        """Close the database connection if it is open."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def initialize(self) -> None:
        """Create all application tables in the database."""
        conn = self.connect()
        create_tables(conn)

    def is_initialized(self) -> bool:
        """Check whether all required tables exist in the database."""
        conn = self.connect()
        return all(table_exists(conn, name) for name in ("raw_data", "processed_data", "reports", "audit_log"))

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement inside a transaction.

        Args:
            sql: SQL statement to execute.
            parameters: Bound parameters for the statement.

        Returns:
            The resulting cursor.
        """
        conn = self.connect()
        with conn:
            cursor = conn.cursor()
            cursor.execute(sql, tuple(parameters))
            conn.commit()
            return cursor

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        """Execute a SQL statement once per parameter sequence.

        Args:
            sql: SQL statement to execute repeatedly.
            seq_of_parameters: Iterable of parameter tuples.

        Returns:
            The resulting cursor.
        """
        conn = self.connect()
        with conn:
            return conn.executemany(sql, [tuple(p) for p in seq_of_parameters])

    def query_all(self, sql: str, parameters: Iterable[Any] = ()) -> List[sqlite3.Row]:
        """Fetch all rows matching a query.

        Args:
            sql: SQL query to execute.
            parameters: Bound parameters for the query.

        Returns:
            List of rows as :class:`sqlite3.Row` objects.
        """
        conn = self.connect()
        return conn.execute(sql, tuple(parameters)).fetchall()

    def query_one(self, sql: str, parameters: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        """Fetch the first row matching a query.

        Args:
            sql: SQL query to execute.
            parameters: Bound parameters for the query.

        Returns:
            The first row, or ``None`` when no rows match.
        """
        conn = self.connect()
        return conn.execute(sql, tuple(parameters)).fetchone()

    # ------------------------------------------------------------------
    # Database insert/query operations used by the rest of the pipeline.
    # ------------------------------------------------------------------

    def insert_raw_data(self, source_file: str, file_hash: str, record_count: int) -> int:
        """Insert a raw-data load record.

        Args:
            source_file: Name of the source file that was loaded.
            file_hash: Content hash of the source file.
            record_count: Number of records loaded.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO raw_data (source_file, file_hash, loaded_at, record_count) VALUES (?, ?, ?, ?)",
            (source_file, file_hash, _utc_now_iso(), record_count),
        )
        return int(cursor.lastrowid)

    def insert_processed_data(
        self, source_file: str, record_count: int, quality_score: Optional[float], payload_json: str
    ) -> int:
        """Insert a processed-data record.

        Args:
            source_file: Name of the source file that produced the data.
            record_count: Number of records processed.
            quality_score: Aggregate data quality score.
            payload_json: JSON-serialized processed records.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO processed_data (source_file, processed_at, record_count, quality_score, payload_json)"
            " VALUES (?, ?, ?, ?, ?)",
            (source_file, _utc_now_iso(), record_count, quality_score, payload_json),
        )
        return int(cursor.lastrowid)

    def insert_report(self, report_type: str, report_path: str, summary: str) -> int:
        """Insert a generated-report tracking record.

        Args:
            report_type: Kind of report (e.g. ``summary`` or ``detailed``).
            report_path: File path where the report was written.
            summary: Short human-readable summary of the report.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO reports (report_type, report_path, generated_at, summary) VALUES (?, ?, ?, ?)",
            (report_type, report_path, _utc_now_iso(), summary),
        )
        return int(cursor.lastrowid)

    def insert_audit_log(self, event_type: str, event_detail: str = "") -> int:
        """Insert an audit-log event.

        Args:
            event_type: Short event identifier.
            event_detail: Optional human-readable detail.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO audit_log (event_type, event_detail, created_at) VALUES (?, ?, ?)",
            (event_type, event_detail, _utc_now_iso()),
        )
        return int(cursor.lastrowid)

    def __enter__(self) -> "DatabaseConnection":
        """Open the connection on context entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close the connection on context exit."""
        self.close()
