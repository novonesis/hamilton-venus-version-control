"""Email notification helpers and Loguru sink for error-level log records.

:func:`send_email_notification` is used directly for ad-hoc emails, while
:class:`ErrorEmailLogHandler` is a callable Loguru sink wired in
``logger_config.py`` to fire whenever an ERROR record is logged.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from config import AppConfig
from loguru import logger


def send_email_notification(
    subject: str,
    body: str,
    recipient: str,
    attachment_path: str | None = None,
) -> None:
    """Send an email notification with an optional attachment.

    Args:
        subject: The subject of the email.
        body: The body text of the email.
        recipient: The email address of the recipient.
        attachment_path: The file path of the attachment. Defaults to ``None``.
    """
    config = AppConfig()
    sender = config.get("smtp_sender", "")
    server_address = config.get("smtp_server", "")
    server_port = config.get("smtp_port", 25)

    # Gracefully skip sending if SMTP is not configured
    if (
        not sender
        or not server_address
        or "example.com" in sender
        or "example.com" in server_address
    ):
        logger.debug("Email notification skipped: SMTP not configured.")
        return

    # Create the email message
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    # Attach a file if the attachment_path is provided
    if attachment_path:
        with open(attachment_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=os.path.basename(attachment_path),
            )

    # Attempt to send the email
    try:
        with smtplib.SMTP(server_address, server_port) as server:
            server.send_message(msg)
            logger.info("Email sent successfully.")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


class ErrorEmailLogHandler:
    """Callable Loguru sink that sends an email notification on each error record.

    Loguru calls :meth:`__call__` for every log record that passes the level
    filter (``level="ERROR"`` is set via ``logger.add()`` in ``logger_config.py``).

    Attributes:
        log_file_path: Path to the log file attached to the notification.
        recipient: Email address to send the notification to.
    """

    def __init__(self, log_file_path: str, recipient: str) -> None:
        self.log_file_path = log_file_path
        self.recipient = recipient

    def __call__(self, message: str) -> None:
        """Forward the error record as an email with the log file attached."""
        subject = "Error Detected in Application Log"
        body = "An error has been detected. Please find the attached log file for more details."
        send_email_notification(subject, body, self.recipient, self.log_file_path)
