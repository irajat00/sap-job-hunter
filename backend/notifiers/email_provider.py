"""
Email notification provider (SMTP) -- free using any existing mailbox
(Gmail app password, personal SMTP, etc.), no paid service. First of
what's designed to be a modular set of providers (see notifiers/base.py) --
adding SMS/Slack/etc. later is a new class implementing the same
`send(to, subject, body)` interface, no other code changes needed.

Configure via SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD in .env.
Empty/unset -> send() returns False and logs a warning, safe no-op.
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText

from notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class EmailNotifier(BaseNotifier):
    def __init__(self, host=None, port=None, user=None, password=None):
        self.host = host or os.getenv("SMTP_HOST", "")
        self.port = int(port or os.getenv("SMTP_PORT", "587"))
        self.user = user or os.getenv("SMTP_USER", "")
        self.password = password or os.getenv("SMTP_PASSWORD", "")

    def send(self, to: str, subject: str, body: str) -> bool:
        if not (self.host and self.user and self.password and to):
            logger.warning("Email notifier not configured or missing recipient -- skipped send.")
            return False
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.user
            msg["To"] = to
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, [to], msg.as_string())
            return True
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return False


NOTIFIER_REGISTRY = {"email": EmailNotifier}


def get_notifier(name: str = "email") -> BaseNotifier:
    cls = NOTIFIER_REGISTRY.get(name, EmailNotifier)
    return cls()
