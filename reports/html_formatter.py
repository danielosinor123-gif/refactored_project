"""HTML report generation and formatting.

Preserves the original HTML report structure: a header block, a Processing
Summary section, and a stats table with Metric/Value rows.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class HTMLFormatter:
    """Builds the HTML report document from summary statistics."""

    def generate_html(self, summary_stats: dict, timestamp: Optional[str] = None) -> str:
        """Generate the HTML report content.

        Args:
            summary_stats: Mapping of statistic names to values.
            timestamp: Optional generation timestamp string. Defaults to now.

        Returns:
            A full HTML document string.
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Data Processing Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; }}
                .stats-table {{ border-collapse: collapse; width: 100%; }}
                .stats-table th, .stats-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                .stats-table th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Data Processing Report</h1>
                <p>Generated: {timestamp}</p>
            </div>

            <div class="section">
                <h2>Processing Summary</h2>
                <table class="stats-table">
                    <tr><th>Metric</th><th>Value</th></tr>
        """.format(timestamp=timestamp)

        for key, value in summary_stats.items():
            html += f"<tr><td>{key}</td><td>{value}</td></tr>"

        html += """
                </table>
            </div>
        </body>
        </html>
        """
        return html


class HTMLReportWriter:
    """Writes HTML reports to disk."""

    def __init__(self, formatter: Optional[HTMLFormatter] = None):
        """Create an HTML report writer.

        Args:
            formatter: Optional custom formatter; defaults to a shared
                :class:`HTMLFormatter` instance.
        """
        self.formatter = formatter or HTMLFormatter()

    def write(self, path: str | Path, summary_stats: dict, timestamp: Optional[str] = None) -> Path:
        """Format and write an HTML report file.

        Args:
            path: Destination file path.
            summary_stats: Mapping of statistic names to values.
            timestamp: Optional generation timestamp string.

        Returns:
            The path of the written report file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        document = self.formatter.generate_html(summary_stats, timestamp)
        path.write_text(document, encoding="utf-8")
        logger.info("HTML report written to %s", path)
        return path


def generate_html_report(summary_stats: dict, timestamp: Optional[str] = None) -> str:
    """Generate the HTML report content.

    Convenience function wrapping :class:`HTMLFormatter`.

    Args:
        summary_stats: Mapping of statistic names to values.
        timestamp: Optional generation timestamp string.

    Returns:
        A full HTML document string.
    """
    return HTMLFormatter().generate_html(summary_stats, timestamp)
