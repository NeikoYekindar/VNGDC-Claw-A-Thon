from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
import mimetypes
import re
import socket
import smtplib
import ssl

from infra_log_sentinel.config import Settings


GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLACEHOLDER_VALUES = {
    "",
    "your_email@gmail.com",
    "replace_with_gmail_app_password",
}


class GmailConfigError(ValueError):
    """Raised when required Gmail SMTP settings are missing."""


class GmailSendError(RuntimeError):
    """Raised when Gmail SMTP accepts config but cannot send the message."""


@dataclass(frozen=True)
class EmailSendResult:
    sent: bool
    dry_run: bool
    message: str


def send_report_email(settings: Settings, report_path: Path, dry_run: bool = False) -> EmailSendResult:
    report_path = Path(report_path)
    if not report_path.exists():
        raise FileNotFoundError(f"Report file not found: {report_path}")

    sender = settings.gmail_address.strip()
    app_password = _normalize_app_password(settings.gmail_app_password)
    recipients = _parse_recipients(settings.report_recipient_email)
    config_errors = _config_errors(sender, app_password, recipients, require_password=not dry_run)
    if config_errors and not dry_run:
        raise GmailConfigError("Invalid Gmail configuration: " + ", ".join(config_errors))

    subject = "Infrastructure Log Sentinel - Daily Log Summary"
    body = (
        "Hello,\n\n"
        "Please find attached the daily Infrastructure Log Sentinel PDF report.\n\n"
        "This report includes log summary, alert classification, probable cause, impact, "
        "and recommended actions for Network, Windows, Linux, and VMware logs.\n\n"
        "Regards,\n"
        "Infrastructure Log Sentinel Agent\n"
    )

    if dry_run:
        recipient_text = ", ".join(recipients) if recipients else "<missing recipient>"
        sender_text = sender if sender else "<missing sender>"
        missing_text = f" Config warnings: {', '.join(config_errors)}." if config_errors else ""
        return EmailSendResult(
            sent=False,
            dry_run=True,
            message=(
                f"Email dry run OK. Would send {report_path.name} from {sender_text} "
                f"to {recipient_text}.{missing_text}"
            ),
        )

    message = _build_email_message(
        sender=sender,
        recipients=recipients,
        subject=subject,
        body=body,
        attachment_path=report_path,
    )

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(
            GMAIL_SMTP_HOST,
            GMAIL_SMTP_PORT,
            local_hostname="localhost",
            timeout=30,
        ) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(sender, app_password)
            smtp.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise GmailSendError(
            "Gmail authentication failed. Verify GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env. "
            "Use a Gmail App Password, not the normal Gmail login password."
        ) from exc
    except smtplib.SMTPException as exc:
        raise GmailSendError(f"Gmail SMTP failed: {exc}") from exc
    except (OSError, TimeoutError, socket.timeout) as exc:
        raise GmailSendError(
            "Gmail network connection failed. Check internet/proxy/firewall access to smtp.gmail.com:587. "
            f"Error: {exc}"
        ) from exc

    return EmailSendResult(
        sent=True,
        dry_run=False,
        message=f"Email sent to {', '.join(recipients)} with attachment {report_path.name}.",
    )


def _build_email_message(
    sender: str,
    recipients: list[str],
    subject: str,
    body: str,
    attachment_path: Path,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    content_type, _ = mimetypes.guess_type(attachment_path.name)
    if content_type:
        maintype, subtype = content_type.split("/", 1)
    else:
        maintype, subtype = "application", "octet-stream"

    with attachment_path.open("rb") as attachment:
        message.add_attachment(
            attachment.read(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment_path.name,
        )

    return message


def _parse_recipients(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _normalize_app_password(value: str) -> str:
    return "".join(value.split())


def _config_errors(sender: str, app_password: str, recipients: list[str], require_password: bool) -> list[str]:
    errors = []
    if _is_missing(sender):
        errors.append("GMAIL_ADDRESS is missing")
    elif not EMAIL_RE.match(sender):
        errors.append("GMAIL_ADDRESS must be a valid email address")

    if require_password and _is_missing(app_password):
        errors.append("GMAIL_APP_PASSWORD is missing")
    elif require_password and len(app_password) != 16:
        errors.append("GMAIL_APP_PASSWORD must be 16 characters after removing spaces")

    if not recipients or any(_is_missing(recipient) for recipient in recipients):
        errors.append("REPORT_RECIPIENT_EMAIL is missing")
    elif any(not EMAIL_RE.match(recipient) for recipient in recipients):
        errors.append("REPORT_RECIPIENT_EMAIL must contain valid email address values")

    return errors


def _is_missing(value: str) -> bool:
    return value.strip() in PLACEHOLDER_VALUES
