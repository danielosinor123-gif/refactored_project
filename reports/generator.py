"""Report orchestration, generation, tracking, and delivery.

Preserves the original behavior: the summary report is a ``.txt`` file with
processing statistics and recently processed files; the detailed report is
an HTML file. Each generated report is logged to the reports table.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from database.connection import DatabaseConnection
from reports.email_sender import EmailSender
from reports.html_formatter import HTMLFormatter, HTMLReportWriter
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """Generates summary and detailed reports and logs them to the database."""

    def __init__(self, db: Optional[DatabaseConnection], report_directory: str | Path,
                 html_writer: Optional[HTMLReportWriter] = None,
                 email_sender: Optional[EmailSender] = None):
        """Create a report generator.

        Args:
            db: Database connection used for report tracking and to list
                recently processed files.
            report_directory: Directory where generated reports are written.
            html_writer: Optional custom HTML writer.
            email_sender: Optional email sender for report delivery.
        """
        self.db = db
        self.report_directory = Path(report_directory)
        self.html_writer = html_writer or HTMLReportWriter(HTMLFormatter())
        self.email_sender = email_sender
        self.reports_generated: List[str] = []

    def generate_summary_report(self, summary_stats: dict, file_name: Optional[str] = None) -> Optional[Path]:
        """Generate a summary ``.txt`` report.

        Args:
            summary_stats: Mapping of statistic names to values.
            file_name: Optional file name. Defaults to
                ``summary_report_{timestamp}.txt``.

        Returns:
            Path of the generated report, or ``None`` on failure.
        """
        try:
            logger.info("Generating summary report")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.report_directory.mkdir(parents=True, exist_ok=True)
            report_path = self.report_directory / (
                file_name or f"summary_report_{timestamp}.txt"
            )
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write("DATA PROCESSING SUMMARY REPORT\n")
                handle.write("=" * 50 + "\n\n")
                handle.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                handle.write("PROCESSING STATISTICS:\n")
                handle.write("-" * 25 + "\n")
                for key, value in summary_stats.items():
                    handle.write(f"{key}: {value}\n")
                handle.write("\n\nFILES PROCESSED:\n")
                handle.write("-" * 20 + "\n")
                if self.db is not None:
                    for row in self.db.fetch_recent_raw_loads(10):
                        handle.write(
                            f"File: {row['source_file']}, Rows: {row['row_count']},"
                            f" Time: {row['timestamp']}\n"
                        )
            self._log_report("summary", str(report_path))
            self.reports_generated.append(str(report_path))
            logger.info("Report generated: %s", report_path)
            return report_path
        except Exception as exc:  # noqa: BLE001 - report failures are logged
            logger.error("Report generation failed: %s", exc)
            return None

    def generate_detailed_report(self, summary_stats: dict, file_name: Optional[str] = None) -> Optional[Path]:
        """Generate a detailed HTML report.

        Args:
            summary_stats: Mapping of statistic names to values.
            file_name: Optional file name. Defaults to
                ``detailed_report_{timestamp}.html``.

        Returns:
            Path of the generated report, or ``None`` on failure.
        """
        try:
            logger.info("Generating detailed report")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.report_directory.mkdir(parents=True, exist_ok=True)
            report_path = self.report_directory / (
                file_name or f"detailed_report_{timestamp}.html"
            )
            html_content = self.html_writer.formatter.generate_html(summary_stats)
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write(html_content)
            self._log_report("detailed", str(report_path))
            self.reports_generated.append(str(report_path))
            logger.info("Report generated: %s", report_path)
            return report_path
        except Exception as exc:  # noqa: BLE001 - report failures are logged
            logger.error("Report generation failed: %s", exc)
            return None

    def _log_report(self, report_type: str, report_path: str) -> None:
        """Record a generated report in the database."""
        if self.db is not None:
            self.db.log_report(report_type, report_path, status="completed")

    def generate_report(self, report_type: str = "summary", summary_stats: Optional[dict] = None) -> Optional[Path]:
        """Generate a report of the given type.

        Args:
            report_type: ``"summary"`` or ``"detailed"``. Defaults to
                ``"summary"``.
            summary_stats: Mapping of statistic names to values.

        Returns:
            Path of the generated report, or ``None`` on failure.
        """
        stats = summary_stats or {}
        if report_type == "detailed":
            return self.generate_detailed_report(stats)
        return self.generate_summary_report(stats)


def generate_report(
    report_type: str = "summary",
    summary_stats: Optional[dict] = None,
    report_directory: Optional[str | Path] = None,
    db: Optional[DatabaseConnection] = None,
) -> Optional[Path]:
    """Generate a report of the given type.

    Convenience function wrapping :class:`ReportGenerator`.

    Args:
        report_type: ``"summary"`` or ``"detailed"``. Defaults to ``"summary"``.
        summary_stats: Mapping of statistic names to values.
        report_directory: Directory where reports are written. Defaults to
            ``reports/`` under the current directory.
        db: Optional database connection for report tracking.

    Returns:
        Path of the generated report, or ``None`` on failure.
    """
    directory = Path(report_directory) if report_directory else Path("reports")
    generator = ReportGenerator(db=db, report_directory=directory)
    return generator.generate_report(report_type, summary_stats)
