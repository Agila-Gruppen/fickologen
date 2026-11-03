"""
Sending email over SMTP.

Configured with environment variables, so any provider works (SendGrid,
Mailgun, Brevo, Gmail, Office 365, ...):

    SMTP_HOST, SMTP_PORT (default 587), SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM (e.g. "Fickologen <noreply@fickologen.se>"),
    SMTP_SECURITY: "starttls" (default), "ssl" or "none"

Without SMTP_HOST nothing is sent and is_configured() is False.
"""
import os
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr


class EmailNotConfigured(Exception):
    """SMTP_HOST is not set."""


def is_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def _ehlo_name() -> str:
    """
    The name this machine gives the mail server. smtplib uses the host name,
    which fails to encode if it has non-ASCII letters (e.g. "kevinAlagöz").
    """
    name = socket.getfqdn()
    return name if name.isascii() else "localhost"


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """
    Sends one email, as plain text and optionally HTML.

    Raises:
        EmailNotConfigured: if SMTP_HOST is not set
        smtplib.SMTPException / OSError: if the server refuses or cannot be reached
    """
    host = os.environ.get("SMTP_HOST")
    if not host:
        raise EmailNotConfigured()
    port = int(os.environ.get("SMTP_PORT", "587"))
    security = os.environ.get("SMTP_SECURITY", "starttls").lower()
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or username or "noreply@localhost"

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=parseaddr(sender)[1].rpartition("@")[2] or None)
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    if security == "ssl":
        server = smtplib.SMTP_SSL(
            host, port, local_hostname=_ehlo_name(), timeout=30, context=ssl.create_default_context()
        )
    else:
        server = smtplib.SMTP(host, port, local_hostname=_ehlo_name(), timeout=30)
    with server:
        if security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if username and password:
            server.login(username, password)
        server.send_message(message)
