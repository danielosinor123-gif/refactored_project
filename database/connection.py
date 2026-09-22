"""SQLite connection management and database initialization.

Connection setup and lifecycle live here; schema statements live in
schemas.py. Row access uses :class:`sqlite3.Row`, matching the original.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, List, Optional

from database.schemas import create_tables, table_exists

_row_factory = sqlite3.Row


class DatabaseConnection:
    """Manages the lifecycle of a SQLite database connection."""

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
        create_tables(self.connect())

    def is_initialized(self) -> bool:
        """Check whether all required tables exist in the database."""
        conn = self.connect()
        return all(table_exists(conn, name) for name in ("raw_data", "processed_data", "reports", "audit_log"))

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> sqlite3.Cursor:
        """Execute a single SQL statement and commit.

        Args:
            sql: SQL statement to execute.
            parameters: Bound parameters for the statement.

        Returns:
            The resulting cursor.
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(parameters))
        conn.commit()
        return cursor

    def query_all(self, sql: str, parameters: Iterable[Any] = ()) -> List[sqlite3.Row]:
        """Fetch all rows matching a query.

        Args:
            sql: SQL query to execute.
            parameters: Bound parameters for the query.

        Returns:
            List of rows as :class:`sqlite3.Row` objects.
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(parameters))
        return cursor.fetchall()

    # ------------------------------------------------------------------
    # Database insert/query operations matching the original fields.
    # ------------------------------------------------------------------

    def log_raw_load(self, source_file: str, data_hash: str, row_count: int, file_size: int) -> int:
        """Insert a raw-data load record.

        Args:
            source_file: Path of the source file that was loaded.
            data_hash: Content hash of the source file.
            row_count: Number of rows loaded.
            file_size: Size of the source file in bytes.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO raw_data (source_file, data_hash, row_count, file_size) VALUES (?, ?, ?, ?)",
            (source_file, data_hash, row_count, file_size),
        )
        return int(cursor.lastrowid)

    def log_processed(
        self,
        raw_data_id: Optional[int],
        transformation_type: str,
        output_file: str,
        quality_score: Optional[float],
    ) -> int:
        """Insert a processed-data record.

        Args:
            raw_data_id: Id of the originating raw_data row.
            transformation_type: Transformation applied (e.g. ``standard``).
            output_file: Path of the exported output file.
            quality_score: Mean data quality score for the export.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO processed_data (raw_data_id, transformation_type, output_file, quality_score)"
            " VALUES (?, ?, ?, ?)",
            (raw_data_id, transformation_type, output_file, quality_score),
        )
        return int(cursor.lastrowid)

    def log_report(
        self,
        report_type: str,
        file_path: str,
        status: str = "completed",
        recipient_email: Optional[str] = None,
    ) -> int:
        """Insert a generated-report tracking record.

        Args:
            report_type: Kind of report (e.g. ``summary`` or ``detailed``).
            file_path: File path where the report was written.
            status: Report status (defaults to ``completed``).
            recipient_email: Optional recipient when the report was emailed.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO reports (report_type, file_path, recipient_email, status) VALUES (?, ?, ?, ?)",
            (report_type, file_path, recipient_email, status),
        )
        return int(cursor.lastrowid)

    def log_audit(
        self,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> int:
        """Insert an audit-log event.

        Args:
            action: Short action identifier.
            user_id: Optional user identifier.
            details: Optional human-readable detail.
            ip_address: Optional originating IP address.

        Returns:
            The inserted row id.
        """
        cursor = self.execute(
            "INSERT INTO audit_log (action, user_id, details, ip_address) VALUES (?, ?, ?, ?)",
            (action, user_id, details, ip_address),
        )
        return int(cursor.lastrowid)

    def fetch_recent_raw_loads(self, limit: int = 10) -> List[sqlite3.Row]:
        """Fetch recent raw-data load records for reporting.

        Args:
            limit: Maximum number of records to return.

        Returns:
            Rows ordered by timestamp descending (newest first).
        """
        return self.query_all(
            "SELECT source_file, timestamp, row_count FROM raw_data ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )

    def __enter__(self) -> "DatabaseConnection":
        """Open the connection on context entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close the connection on context exit."""
        self.close()
