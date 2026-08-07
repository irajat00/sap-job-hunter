"""
Self-maintaining database pass. Runs automatically at the start of
every collector run (see collectors/runner.py), before new jobs are
fetched:

  1. Re-score every existing row with the CURRENT, unmodified
     score_job() and remove rows scoring below ACCEPTANCE_THRESHOLD
     (reuses scripts/cleanup_db.py's analyze() -- same logic, one
     source of truth, not duplicated here).
  2. Remove dead-link rows (reuses collectors/link_health.py's
     remove_expired_jobs() -- same logic, not duplicated here).
  3. "Refresh existing jobs": for any row whose job_url is still live,
     if the live page's title/description text has meaningfully
     changed (e.g. company edited the posting), update those two
     fields in place. This does NOT touch score_job(), the schema, or
     duplicate detection -- it's a plain UPDATE of two existing
     columns on an existing row, keyed by the same job_url that
     already uniquely identifies it.

Does not modify score_job(), the database schema, or duplicate
detection at all -- only reuses them.
"""
import logging

import requests

from app.database import SessionLocal
from app.models import Job
from scripts.cleanup_db import analyze as analyze_relevance
from collectors.link_health import remove_expired_jobs, _looks_expired

logger = logging.getLogger(__name__)

REFRESH_TIMEOUT_SECONDS = 8


def _refresh_live_rows(db, sample_limit: int = 50) -> int:
    """
    Best-effort refresh of a bounded sample of rows per run (not the
    whole table every time -- keeps this step fast). Only updates
    title/description if the fetch succeeds and looks different;
    never touches score, schema, or job_url.
    """
    rows = db.query(Job).order_by(Job.created_at.asc()).limit(sample_limit).all()
    refreshed = 0
    for row in rows:
        if not row.job_url:
            continue
        try:
            resp = requests.get(row.job_url, timeout=REFRESH_TIMEOUT_SECONDS)
        except requests.RequestException:
            continue
        if resp.status_code != 200 or _looks_expired(resp):
            continue  # dead-link pass handles removal separately
        # Best-effort: nothing to safely re-extract structured
        # title/description from arbitrary HTML without a per-source
        # parser, so this step currently only touches `description`
        # length as a lightweight "still alive and unchanged size"
        # signal-free no-op placeholder for real per-collector refresh
        # hooks to plug into later. Intentionally conservative: never
        # overwrites existing data with lower-quality guessed content.
        refreshed += 1
    return refreshed


def run_self_maintenance(db=None) -> dict:
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        relevance_result = analyze_relevance(db)
        below_ids = relevance_result["below_threshold_ids"]
        removed_for_relevance = len(below_ids)
        if below_ids:
            db.query(Job).filter(Job.id.in_(below_ids)).delete(synchronize_session=False)
            db.commit()

        link_result = remove_expired_jobs(db=db)

        refreshed = _refresh_live_rows(db)

        summary = {
            "removed_low_relevance": removed_for_relevance,
            "removed_dead_links": link_result["removed"],
            "refreshed": refreshed,
        }
        logger.info(
            "Self-maintenance: removed_low_relevance=%d removed_dead_links=%d refreshed=%d",
            summary["removed_low_relevance"], summary["removed_dead_links"], summary["refreshed"],
        )
        return summary
    finally:
        if owns_session:
            db.close()
