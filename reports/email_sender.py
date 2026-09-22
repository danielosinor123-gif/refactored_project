"""Email composition, report attachment, and SMTP sending."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Optional, Sequence

from utils.logging_setup import get_logger

logger = get_logger(__name__)


class EmailSender:
    """Composes report emails and sends them over SMTP."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender: str,
        recipients: Sequence[str],
        username: str = "",
        password: str = "",
        use_tls: bool = True,
        timeout_seconds: int = 30,
    ):
        """Create an email sender.

        Args:
            smtp_server: SMTP host name.
            smtp_port: SMTP port (587 for STARTTLS typically).
            sender: From address.
            recipients: List of To addresses.
            username: Optional SMTP username (from environment/config).
            password: Optional SMTP password (from environment/config).
            use_tls: Whether to upgrade the connection with STARTTLS.
            timeout_seconds: SMTP connection timeout in seconds.
        """
        self.smtp_server = smtp_server
        self.smtp_port = int(smtp_port)
        self.sender = sender
        self.recipients = list(recipients)
        self.username = username
        self.password = password
        self.use_tls = bool(use_tls)
        self.timeout_seconds = int(timeout_seconds)

    def compose_email(self, subject: str, body: str, attachment_path: Optional[str | Path] = None) -> EmailMessage:
        """Compose an email message with an optional report attachment.

        Args:
            subject: Email subject line.
            body: Plain-text email body.
            attachment_path: Optional path to a file to attach.

        Returns:
            The composed :class:`~email.message.EmailMessage`.

        Raises:
            FileNotFoundError: When ``attachment_path`` does not exist.
        """
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = ", ".join(self.recipients)
        message["Subject"] = subject
        message.set_content(body)
        if attachment_path is not None:
            path = Path(attachment_path)
            if not path.is_file():
                raise FileNotFoundError(f"Attachment not found: {path}")
            data = path.read_bytes()
            message.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=path.name,
            )
        return message

    def send(self, message: EmailMessage) -> bool:
        """Send a composed message over SMTP.

        Args:
            message: The message to send.

        Returns:
            ``True`` when sending succeeded, ``False`` otherwise. Errors are
            logged, never raised, to keep the pipeline running.
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.timeout_seconds) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(message)
        except smtplib.SMTPException as exc:
            logger.error("SMTP error while sending email: %s", exc)
            return False
        except OSError as exc:
            logger.error("Connection error while sending email: %s", exc)
            return False
        logger.info("Email sent to %s", message["To"])
        return True

    def send_email_report(
        self,
        subject: str,
        body: str,
        attachment_path: Optional[str | Path] = None,
    ) -> bool:
        """Compose and send a report email in one step.

        Args:
            subject: Email subject line.
            body: Plain-text email body.
            attachment_path: Optional path to a report file to attach.

        Returns:
            ``True`` when sending succeeded, ``False`` otherwise.
        """
        if not self.recipients:
            logger.warning("No email recipients configured; skipping report email")
            return False
        try:
            message = self.compose_email(subject, body, attachment_path)
        except FileNotFoundError as exc:
            logger.error("Cannot send report email: %s", exc)
            return False
        return self.send(message)

    send_report = send_email_report
