"""
Checks existing saved job postings' URLs for expiry and removes rows
that are no longer live. Called automatically at the end of
collectors.runner.run(), so the database self-cleans over time.

Does NOT touch the database schema: expired rows are deleted outright
rather than "marked inactive", since Job has no active/inactive column
and adding one would be a schema change (explicitly out of scope for
this change -- see the instruction to only remove or mark inactive,
combined with "do not modify database schema").

A row is considered expired if its job_url:
    - returns HTTP 404 or 410, or
    - returns HTTP 200 but the response body contains one of a small
      set of "this posting is gone" phrases some job boards use
      instead of a proper HTTP status code.

Network errors/timeouts are deliberately NOT treated as expiry -- a
transient failure to reach the URL doesn't mean the posting is gone,
so those rows are left alone and just logged.
"""
import logging

import requests

from app.database import SessionLocal
from app.models import Job

logger = logging.getLogger(__name__)

EXPIRY_STATUS_CODES = {404, 410}

EXPIRY_TEXT_MARKERS = [
    "job no longer available",
    "position no longer available",
    "this vacancy has expired",
]

REQUEST_TIMEOUT_SECONDS = 10


def _looks_expired(response) -> bool:
    if response.status_code in EXPIRY_STATUS_CODES:
        return True
    if response.status_code == 200:
        body_lower = response.text.lower()
        if any(marker in body_lower for marker in EXPIRY_TEXT_MARKERS):
            return True
    return False


def remove_expired_jobs(db=None) -> dict:
    """
    Sweeps every stored job_url and deletes rows that look expired.
    Returns {"checked": int, "removed": int, "errors": int}.

    Pass an existing SQLAlchemy session via `db` to reuse one already
    open (e.g. from within collectors.runner.run()); otherwise a new
    session is opened and closed here.
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    summary = {"checked": 0, "removed": 0, "errors": 0}
    try:
        jobs = db.query(Job).all()
        for row in jobs:
            summary["checked"] += 1
            if not row.job_url:
                continue
            try:
                resp = requests.get(row.job_url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
            except requests.RequestException as exc:
                summary["errors"] += 1
                logger.debug("Link check failed (not treated as expired, skipped): %s -- %s", row.job_url, exc)
                continue

            if _looks_expired(resp):
                logger.info("Removing expired job: %s (%s)", row.title, row.job_url)
                db.delete(row)
                summary["removed"] += 1

        db.commit()
    finally:
        if owns_session:
            db.close()

    logger.info(
        "Expired-link sweep done. checked=%d removed=%d errors=%d",
        summary["checked"], summary["removed"], summary["errors"],
    )
    return summary
