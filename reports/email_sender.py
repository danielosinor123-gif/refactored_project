"""Email composition, report attachment, and SMTP sending.

Preserves the original email behavior: MIME multipart message with the
report attached, STARTTLS upgrade, login, and send. Errors are logged,
never raised, to keep the pipeline running.
"""

from __future__ import annotations

import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from utils.logging_setup import get_logger

logger = get_logger(__name__)

REPORT_BODY = """
Dear User,

Please find attached the latest data processing report.

Best regards,
Data Processing System
"""


class EmailSender:
    """Composes report emails and sends them over SMTP."""

    def __init__(self, email_server: str = "smtp.gmail.com", email_port: int = 587,
                 email_user: str = "", email_password: str = ""):
        """Create an email sender.

        Args:
            email_server: SMTP host name.
            email_port: SMTP port (587 for STARTTLS).
            email_user: SMTP username / from address.
            email_password: SMTP password (from environment/config).
        """
        self.email_server = email_server
        self.email_port = int(email_port)
        self.email_user = email_user
        self.email_password = email_password

    def compose_email(self, report_path: str | Path, recipient_email: str,
                      subject: Optional[str] = None) -> MIMEMultipart:
        """Compose an email message with the report attached.

        Args:
            report_path: Path to the report file to attach.
            recipient_email: To address.
            subject: Optional subject line. Defaults to the original subject.

        Returns:
            The composed :class:`~email.mime.multipart.MIMEMultipart`.

        Raises:
            FileNotFoundError: When ``report_path`` does not exist.
        """
        if subject is None:
            subject = f"Data Processing Report - {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}"
        msg = MIMEMultipart()
        msg["From"] = self.email_user
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(REPORT_BODY, "plain"))

        path = Path(report_path)
        if not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")
        with open(path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename= {path.name}")
        msg.attach(part)
        return msg

    def send_email_report(self, report_path: str | Path, recipient_email: str) -> bool:
        """Compose and send a report email in one step.

        Args:
            report_path: Path to the report file to attach.
            recipient_email: To address.

        Returns:
            ``True`` when sending succeeded, ``False`` otherwise.
        """
        try:
            logger.info("Sending report to %s", recipient_email)
            msg = self.compose_email(report_path, recipient_email)
            server = smtplib.SMTP(self.email_server, self.email_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            text = msg.as_string()
            server.sendmail(self.email_user, recipient_email, text)
            server.quit()
            logger.info("Email sent successfully")
            return True
        except Exception as exc:  # noqa: BLE001 - email failures are logged
            logger.error("Email sending failed: %s", exc)
            return False


def send_email_report(
    report_path: str | Path,
    recipient_email: str,
    email_server: str = "smtp.gmail.com",
    email_port: int = 587,
    email_user: str = "",
    email_password: str = "",
) -> bool:
    """Compose and send a report email.

    Convenience function wrapping :class:`EmailSender`.

    Args:
        report_path: Path to the report file to attach.
        recipient_email: To address.
        email_server: SMTP host name.
        email_port: SMTP port.
        email_user: SMTP username / from address.
        email_password: SMTP password (from environment/config).

    Returns:
        ``True`` when sending succeeded, ``False`` otherwise.
    """
    sender = EmailSender(email_server, email_port, email_user, email_password)
    return sender.send_email_report(report_path, recipient_email)
