"""HTML report generation and formatting."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class HTMLFormatter:
    """Builds HTML documents from report data and DataFrames."""

    def escape(self, text: str) -> str:
        """Escape text for safe inclusion in an HTML document.

        Args:
            text: Raw text to escape.

        Returns:
            HTML-escaped text.
        """
        return html.escape(str(text))

    def format_table(self, frame: pd.DataFrame, max_rows: int = 25) -> str:
        """Format a DataFrame as an HTML table.

        Args:
            frame: DataFrame to render.
            max_rows: Maximum number of rows to include.

        Returns:
            HTML markup for the table (empty string when the frame is empty).
        """
        if frame is None or frame.empty:
            return ""
        preview = frame.head(max_rows)
        header = "".join(f"<th>{self.escape(column)}</th>" for column in preview.columns)
        rows = []
        for _, row in preview.iterrows():
            cells = "".join(f"<td>{self.escape(value)}</td>" for value in row)
            rows.append(f"<tr>{cells}</tr>")
        return (
            '<table class="data-table">'
            f"<thead><tr>{header}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )

    def format_statistics(self, statistics: dict) -> str:
        """Format a statistics dictionary as an HTML definition list.

        Args:
            statistics: Mapping of statistic names to values.

        Returns:
            HTML markup for the statistics section.
        """
        if not statistics:
            return ""
        items = "".join(
            f"<dt>{self.escape(key)}</dt><dd>{self.escape(value)}</dd>"
            for key, value in statistics.items()
        )
        return f'<dl class="stats">{items}</dl>'

    def format_document(
        self,
        title: str,
        summary: str,
        statistics: Optional[dict] = None,
        table_html: str = "",
    ) -> str:
        """Build a complete HTML report document.

        Args:
            title: Report title.
            summary: Plain-text summary paragraph.
            statistics: Optional statistics mapping.
            table_html: Optional pre-rendered table HTML (e.g. from
                :meth:`format_table`).

        Returns:
            A full HTML document string.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{self.escape(title)}</title>
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 2rem; color: #222; }}
h1 {{ border-bottom: 2px solid #4a7; padding-bottom: 0.4rem; }}
.meta {{ color: #666; font-size: 0.9rem; }}
dl.stats {{ display: grid; grid-template-columns: max-content 1fr; gap: 0.3rem 1rem; }}
dt {{ font-weight: 600; }}
dd {{ margin: 0; }}
table.data-table {{ border-collapse: collapse; margin-top: 1rem; width: 100%; }}
table.data-table th, table.data-table td {{ border: 1px solid #ccc; padding: 0.35rem 0.6rem; text-align: left; }}
table.data-table th {{ background: #f0f4f0; }}
</style>
</head>
<body>
<h1>{self.escape(title)}</h1>
<p class="meta">Generated {self.escape(timestamp)}</p>
<p>{self.escape(summary)}</p>
{self.format_statistics(statistics or {})}
{table_html}
</body>
</html>
"""


class HTMLReportWriter:
    """Writes formatted HTML reports to disk."""

    def __init__(self, formatter: Optional[HTMLFormatter] = None):
        """Create an HTML report writer.

        Args:
            formatter: Optional custom formatter; defaults to a shared
                :class:`HTMLFormatter` instance.
        """
        self.formatter = formatter or HTMLFormatter()

    def write(self, path: str | Path, title: str, summary: str, statistics: Optional[dict] = None,
              table_html: str = "") -> Path:
        """Format and write an HTML report file.

        Args:
            path: Destination file path.
            title: Report title.
            summary: Plain-text summary paragraph.
            statistics: Optional statistics mapping.
            table_html: Optional pre-rendered table HTML.

        Returns:
            The path of the written report file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        document = self.formatter.format_document(title, summary, statistics, table_html)
        path.write_text(document, encoding="utf-8")
        logger.info("HTML report written to %s", path)
        return path
