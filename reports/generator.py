"""Report orchestration, generation, tracking, and delivery."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from database.connection import DatabaseConnection
from reports.email_sender import EmailSender
from reports.html_formatter import HTMLFormatter, HTMLReportWriter
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """Generates summary and detailed reports and logs them to the database."""

    def __init__(
        self,
        db: DatabaseConnection,
        report_directory: str | Path,
        html_writer: Optional[HTMLReportWriter] = None,
        email_sender: Optional[EmailSender] = None,
    ):
        """Create a report generator.

        Args:
            db: Database connection used for report tracking records.
            report_directory: Directory where generated reports are written.
            html_writer: Optional custom HTML writer.
            email_sender: Optional email sender used when email is enabled.
        """
        self.db = db
        self.report_directory = Path(report_directory)
        self.html_writer = html_writer or HTMLReportWriter(HTMLFormatter())
        self.email_sender = email_sender

    def _report_path(self, name: str) -> Path:
        """Build a report file path inside the report directory."""
        return self.report_directory / name

    def _log_report(self, report_type: str, path: Path, summary: str) -> None:
        """Record a generated report in the database."""
        self.db.insert_report(report_type, str(path), summary)

    def generate_summary_report(
        self,
        statistics: dict,
        file_name: str = "summary_report.html",
        send_email: bool = False,
    ) -> Optional[Path]:
        """Generate a summary report from pipeline statistics.

        Args:
            statistics: Mapping of statistic names to values.
            file_name: Destination file name inside the report directory.
            send_email: Whether to email the generated report.

        Returns:
            Path of the generated report, or ``None`` on failure.
        """
        summary = self._build_summary_text(statistics)
        try:
            path = self.html_writer.write(
                self._report_path(file_name),
                title="Data Processing Summary Report",
                summary=summary,
                statistics=statistics,
            )
        except OSError as exc:
            logger.error("Failed to write summary report: %s", exc)
            return None
        self._log_report("summary", path, summary)
        if send_email:
            self._email_report("Data Processing Summary Report", path, summary)
        return path

    def generate_detailed_report(
        self,
        frame: pd.DataFrame,
        statistics: dict,
        file_name: str = "detailed_report.html",
        send_email: bool = False,
        max_rows: int = 25,
    ) -> Optional[Path]:
        """Generate a detailed report including a data preview table.

        Args:
            frame: Processed DataFrame to preview in the report.
            statistics: Mapping of statistic names to values.
            file_name: Destination file name inside the report directory.
            send_email: Whether to email the generated report.
            max_rows: Maximum number of preview rows to include.

        Returns:
            Path of the generated report, or ``None`` on failure.
        """
        summary = self._build_summary_text(statistics)
        formatter = self.html_writer.formatter
        table_html = formatter.format_table(frame, max_rows=max_rows)
        try:
            path = self.html_writer.write(
                self._report_path(file_name),
                title="Data Processing Detailed Report",
                summary=summary,
                statistics=statistics,
                table_html=table_html,
            )
        except OSError as exc:
            logger.error("Failed to write detailed report: %s", exc)
            return None
        self._log_report("detailed", path, summary)
        if send_email:
            self._email_report("Data Processing Detailed Report", path, summary)
        return path

    def _build_summary_text(self, statistics: dict) -> str:
        """Build a one-paragraph summary line from statistics."""
        if not statistics:
            return "No statistics were produced for this run."
        parts = [f"{key}: {value}" for key, value in statistics.items()]
        return " | ".join(parts)

    def _email_report(self, title: str, path: Path, summary: str) -> bool:
        """Email a generated report when an email sender is configured."""
        if self.email_sender is None:
            logger.info("Email sender not configured; skipping email for %s", path.name)
            return False
        return self.email_sender.send_report(
            subject=f"{title} - {Path(path).name}",
            body=f"The generated report is attached.\n\n{summary}",
            attachment_path=path,
        )
