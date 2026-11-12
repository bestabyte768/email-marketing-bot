"""SMTP email sending."""

from __future__ import annotations

import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import refresh_settings

VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def render_template(text: str, variables: dict) -> str:
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    return VAR_RE.sub(replacer, text)


def send_email(to_email: str, subject: str, body: str) -> None:
    cfg = refresh_settings()
    if not cfg.smtp_user or not cfg.smtp_password:
        raise RuntimeError("SMTP credentials are not configured. Check your .env file.")

    from_addr = cfg.smtp_from or cfg.smtp_user
    message = MIMEMultipart("alternative")
    message["From"] = from_addr
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
        if cfg.smtp_use_tls:
            server.starttls()
        server.login(cfg.smtp_user, cfg.smtp_password)
        server.sendmail(from_addr, [to_email], message.as_string())
