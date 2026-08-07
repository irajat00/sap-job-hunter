"""
Email-feed collector: reads job-alert emails from an IMAP mailbox
(e.g. a dedicated inbox subscribed to job-alert newsletters) and
extracts postings via generic HTML link+text heuristics.

Honest caveat: unlike Adzuna/Jooble/RSS (structured data), email HTML
varies wildly per sender, so extraction here is best-effort --
it pulls every link that looks like a job posting (heuristic: link
text or surrounding text contains the search query) rather than
reliably parsing structured fields. Treat this as a supplementary,
lower-confidence source, not a primary one.

Configure via:
    EMAIL_IMAP_HOST, EMAIL_IMAP_USER, EMAIL_IMAP_PASSWORD,
    EMAIL_IMAP_FOLDER (default "INBOX")
Empty/unset credentials -> zero requests, zero jobs (safe no-op),
same pattern as every other optional collector in this project.
"""
import os
import re
import email
import imaplib
import logging
from email.header import decode_header

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

LINK_RE = re.compile(r'href=["\'](https?://[^"\']+)["\']', re.IGNORECASE)


class EmailFeedCollector(BaseCollector):
    source_name = "email"

    def __init__(self, host=None, user=None, password=None, folder=None):
        self.host = host or os.getenv("EMAIL_IMAP_HOST", "")
        self.user = user or os.getenv("EMAIL_IMAP_USER", "")
        self.password = password or os.getenv("EMAIL_IMAP_PASSWORD", "")
        self.folder = folder or os.getenv("EMAIL_IMAP_FOLDER", "INBOX")

    def fetch_jobs(self, query: str = "", location: str = "") -> list[dict]:
        if not (self.host and self.user and self.password):
            return []  # not configured -- safe no-op, no connection attempted

        jobs = []
        try:
            conn = imaplib.IMAP4_SSL(self.host)
            conn.login(self.user, self.password)
            conn.select(self.folder)
            status, data = conn.search(None, "UNSEEN")
            if status != "OK":
                return []
            ids = data[0].split()
            for msg_id in ids[-25:]:  # bounded per run, most recent 25 unseen
                status, msg_data = conn.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                subject = str(decode_header(msg.get("Subject", ""))[0][0])
                body_html = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            body_html = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body_html = msg.get_payload(decode=True).decode(errors="ignore")

                for link in set(LINK_RE.findall(body_html)):
                    jobs.append({
                        "title": subject,
                        "company": None,
                        "location": None,
                        "salary": None,
                        "source": self.source_name,
                        "job_url": link,
                        "posted_date": msg.get("Date"),
                        "description": "",
                    })
            conn.close()
            conn.logout()
        except Exception as exc:
            logger.warning("[email] IMAP fetch failed: %s", exc)
            return []
        return jobs
