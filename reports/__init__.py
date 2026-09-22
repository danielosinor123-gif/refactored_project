"""Reports package: generation, HTML formatting, and email delivery."""

from reports.email_sender import EmailSender
from reports.generator import ReportGenerator, generate_report
from reports.html_formatter import HTMLFormatter, HTMLReportWriter, generate_html_report

__all__ = [
    "ReportGenerator",
    "HTMLFormatter",
    "HTMLReportWriter",
    "EmailSender",
    "generate_report",
    "generate_html_report",
]
