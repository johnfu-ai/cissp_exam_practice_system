"""Outbound email (password-reset links). SMTP via env; empty host = NullMailer."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, *, to: str, subject: str, body_text: str) -> None: ...


class NullMailer:
    def send(self, *, to: str, subject: str, body_text: str) -> None:
        logger.info("mail skipped (no smtp_host): to=%s subject=%s", to, subject)


class SmtpMailer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        mail_from: str,
        use_tls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = mail_from
        self._use_tls = use_tls

    def send(self, *, to: str, subject: str, body_text: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = to
        msg.set_content(body_text)
        with smtplib.SMTP(self._host, self._port, timeout=15) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(msg)


def build_mailer() -> Mailer:
    host = (settings.smtp_host or "").strip()
    if not host:
        return NullMailer()
    mail_from = (settings.smtp_from or "").strip() or "noreply@localhost"
    return SmtpMailer(
        host=host,
        port=settings.smtp_port,
        user=settings.smtp_user,
        password=settings.smtp_password,
        mail_from=mail_from,
        use_tls=settings.smtp_use_tls,
    )
