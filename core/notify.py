"""
Optional email notifications via SMTP.
Reads SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS from environment.
Silently skips if not configured.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER"))


def send_high_severity_alert(issue_id: int, issue_type: str, area: str, admin_emails: list[str]) -> None:
    """Send HTML alert to admins for a new High-severity issue."""
    if not _smtp_configured() or not admin_emails:
        return
    subject = f"[UrbanLens] High-Severity Issue Reported: {issue_type} in {area}"
    body = f"""
    <html><body style="font-family:sans-serif;color:#0B2545">
      <h2 style="color:#C8372D">High-Severity Issue Detected</h2>
      <p>A new <strong>{issue_type}</strong> issue has been reported in <strong>{area}</strong>.</p>
      <p><strong>Issue ID:</strong> #{issue_id}</p>
      <p>Please log in to UrbanLens to review and assign this issue.</p>
      <hr>
      <p style="color:#5B6B7F;font-size:12px">UrbanLens — Seeing what the city needs fixed.</p>
    </body></html>
    """
    _send(admin_emails, subject, body)


def send_export_csv(recipient: str, csv_content: str, filename: str = "export.csv") -> None:
    """Email a CSV file to a user."""
    if not _smtp_configured():
        return
    from email.mime.base import MIMEBase  # noqa: PLC0415
    from email import encoders  # noqa: PLC0415
    msg = MIMEMultipart()
    msg["Subject"] = f"[UrbanLens] Exported data: {filename}"
    msg["From"] = os.environ.get("SMTP_USER", "noreply@urbanlens.app")
    msg["To"] = recipient
    msg.attach(MIMEText("<p>Please find the export attached.</p>", "html"))
    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_content.encode())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)
    _send_msg(msg, [recipient])


def _send(to: list[str], subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_USER", "noreply@urbanlens.app")
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(html_body, "html"))
    _send_msg(msg, to)


def _send_msg(msg, to: list[str]) -> None:
    host = os.environ.get("SMTP_HOST", "localhost")
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER", "")
    pwd  = os.environ.get("SMTP_PASS", "")
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            if port == 587:
                server.starttls()
            if user and pwd:
                server.login(user, pwd)
            server.sendmail(msg["From"], to, msg.as_string())
    except Exception:
        pass  # never crash the app on email failure
