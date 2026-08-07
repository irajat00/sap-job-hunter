"""
Runs every registered BaseCollector across the full keyword x location
matrix (app/config.py), filters out irrelevant SAP-module postings
(app/relevance.py), dedupes against the database by job_url, saves new
rows, sweeps existing saved jobs for expired links
(collectors/link_health.py), and sends an immediate Telegram
notification for every NEW job saved this run.

Usage:
    python -m collectors.runner
    python -m collectors.runner --query "SAP PP Consultant" --location "Dubai"   # single override, skips the matrix
    python -m collectors.runner --no-notify                                       # skip Telegram
    python -m collectors.runner --skip-expiry-check                               # skip the expired-link sweep

To add a source once it's implemented: import its collector class and
add an instance to COLLECTORS below. Everything else -- the search
matrix, relevance filter, dedup, saving, expiry sweep, notifications,
the CLI -- stays the same.

=== Telegram notification rules ===
Telegram is the primary feature. For every job that is genuinely NEW
this run (not already in the database by job_url): the job is saved
AND a Telegram notification is sent immediately, one message per job
(never batched).
Duplicate protection is two-layered:
    1. In-memory: `existing_urls` already prevents the same job_url
       from being treated as "new" twice within a single run.
    2. Persisted: Job.telegram_notified is flipped to 1 in the database
       the moment a notification is sent successfully. Since a job that
       was saved in a previous run is never "new" again, re-running the
       collector (or crashing mid-run and re-running) can never resend
       a notification for a job that already has one.
"""
import argparse
import itertools
import logging
import time

import app.env  # noqa: F401  (loads .env as an import side effect, before any collector/notifier reads env vars)

from sqlalchemy.exc import IntegrityError

from app.config import KEYWORDS, LOCATIONS
from app.database import SessionLocal
from app.models import Job
from app.relevance import filter_relevant, score_job
from collectors.adzuna import AdzunaCollector
from collectors.jooble import JoobleCollector
from collectors.rss_feed import RSSFeedCollector
from collectors.email_feed import EmailFeedCollector
from collectors.greenhouse import GreenhouseCollector
from collectors.lever import LeverCollector
from collectors.ashby import AshbyCollector
from collectors.smartrecruiters import SmartRecruitersCollector
from collectors.link_health import remove_expired_jobs
from notifiers import telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("runner")

# Each entry is an instantiated BaseCollector.
#
# JoobleCollector needs JOOBLE_API_KEY (free, see collectors/jooble.py)
# -- without it, it errors clearly per combo, exactly like Adzuna
# without credentials, and is logged/skipped rather than crashing the
# run.
#
# GreenhouseCollector/LeverCollector/AshbyCollector/SmartRecruitersCollector
# are safe no-ops unless their company-list env vars are set (see
# app/config.py).
#
# Add more as they're built:
#   COLLECTORS = [AdzunaCollector(), NaukriCollector(), JSearchCollector()]
COLLECTORS = [
    AdzunaCollector(),
    JoobleCollector(),
    RSSFeedCollector(),          # safe no-op unless RSS_FEED_URLS is set
    EmailFeedCollector(),        # safe no-op unless EMAIL_IMAP_* is set
    GreenhouseCollector(),       # safe no-op unless GREENHOUSE_COMPANIES is set
    LeverCollector(),            # safe no-op unless LEVER_COMPANIES is set
    AshbyCollector(),            # safe no-op unless ASHBY_COMPANIES is set
    SmartRecruitersCollector(),  # safe no-op unless SMARTRECRUITERS_COMPANIES is set
]

# Adzuna's free tier is rate-limited; a small gap between calls avoids
# tripping it during a full sweep of the keyword x location matrix.
REQUEST_DELAY_SECONDS = 1.0


def run(query: str = None, location: str = None, notify: bool = True, check_expired: bool = True) -> dict:
    """
    Runs every registered collector.

    If `query`/`location` are given, runs that single search (useful for
    testing). Otherwise sweeps the full KEYWORDS x LOCATIONS matrix from
    app/config.py.

    If `check_expired` is True (default), also sweeps every existing
    saved job_url at the end of the run and removes rows that look
    expired (see collectors/link_health.py) -- this can add
    significant runtime for a large database, since it makes one HTTP
    request per stored job, so pass check_expired=False (or
    --skip-expiry-check on the CLI) to skip it for a quick run.

    If `notify` is True (default), every newly-saved job gets an
    individual Telegram notification immediately. See the module
    docstring for the full notification/duplicate-protection rules.

    Returns a summary dict.
    """
    db = SessionLocal()
    from collectors.self_maintain import run_self_maintenance
    self_maint_summary = run_self_maintenance(db=db)
    summary = {"fetched": 0, "filtered_out": 0, "saved": 0, "duplicates": 0, "errors": [], "expired_removed": 0,
               "notified": 0, "self_maintenance": self_maint_summary}
    # Relevance scores of every job that passed the filter this run --
    # purely in-memory, purely for the end-of-run summary below. Never
    # attached to a job dict, never persisted, never returned by the
    # API. See app/relevance.py's score_job() docstring.
    accepted_scores = []

    searches = [(query, location or "")] if query else list(itertools.product(KEYWORDS, LOCATIONS))

    try:
        existing_urls = {row[0] for row in db.query(Job.job_url).all()}
        from collectors.resilience import call_with_resilience
        from app.monitoring.models import CollectorRun
        collector_stats = {}  # source_name -> tally dict, written to CollectorRun at the end

        # Newly-created Job ORM rows for jobs saved this run, kept
        # around (post-commit, so they have ids) purely so we can
        # notify against them and flip telegram_notified individually.
        newly_saved_rows = []

        for collector in COLLECTORS:
            name = collector.source_name
            collector_stats.setdefault(name, {"fetched": 0, "accepted": 0, "rejected": 0, "removed": 0, "error": None})

            for kw, loc in searches:
                jobs, err = call_with_resilience(collector.fetch_jobs, query=kw, location=loc, source_name=name)
                if err:
                    logger.error("Collector '%s' failed for (%r, %r): %s", name, kw, loc, err)
                    summary["errors"].append(f"{name} [{kw} / {loc}]: {err}")
                    collector_stats[name]["error"] = err
                    continue

                summary["fetched"] += len(jobs)
                collector_stats[name]["fetched"] += len(jobs)

                jobs, dropped = filter_relevant(jobs)
                summary["filtered_out"] += dropped
                collector_stats[name]["accepted"] += len(jobs)
                collector_stats[name]["rejected"] += dropped
                accepted_scores.extend(score_job(j) for j in jobs)

                new_rows = []
                for job in jobs:
                    url = job.get("job_url")
                    if not url:
                        continue  # can't dedupe without a URL, skip
                    if url in existing_urls:
                        summary["duplicates"] += 1
                        continue

                    row = Job(**job, telegram_notified=0)
                    new_rows.append(row)
                    existing_urls.add(url)  # guard against dupes within this same run

                if new_rows:
                    try:
                        db.add_all(new_rows)
                        db.commit()
                        summary["saved"] += len(new_rows)
                        newly_saved_rows.extend(new_rows)
                    except IntegrityError:
                        # Belt-and-suspenders: the in-memory existing_urls set
                        # should already prevent this, but if a duplicate
                        # job_url slips through (e.g. a race with another
                        # process), fall back to inserting row-by-row so one
                        # bad row doesn't drop the whole batch.
                        db.rollback()
                        saved_in_fallback = 0
                        for row in new_rows:
                            try:
                                db.add(row)
                                db.commit()
                                saved_in_fallback += 1
                                newly_saved_rows.append(row)
                            except IntegrityError:
                                db.rollback()
                                summary["duplicates"] += 1
                                logger.warning(
                                    "Duplicate job_url rejected by DB constraint: %s", row.job_url
                                )
                        summary["saved"] += saved_in_fallback

                logger.info(
                    "'%s' [%s / %s]: fetched=%d new=%d",
                    name, kw, loc or "any", len(jobs), len(new_rows),
                )

                if REQUEST_DELAY_SECONDS:
                    time.sleep(REQUEST_DELAY_SECONDS)

        logger.info(
            "Done. fetched=%d filtered_out=%d saved=%d duplicates=%d errors=%d",
            summary["fetched"], summary["filtered_out"], summary["saved"],
            summary["duplicates"], len(summary["errors"]),
        )

        # Collector summary. "Filtered" and "Rejected" both refer to the
        # same underlying count here -- the relevance filter doesn't
        # currently distinguish "filtered for quality" from "rejected
        # outright" as two separate reasons, so both lines report the
        # same number rather than inventing an artificial split.
        accepted_count = summary["fetched"] - summary["filtered_out"]
        from datetime import datetime, timezone as _tz
        for src, stats in collector_stats.items():
            db.add(CollectorRun(
                source=src, finished_at=datetime.now(_tz.utc),
                fetched=stats["fetched"], accepted=stats["accepted"],
                rejected=stats["rejected"], removed=self_maint_summary.get("removed_dead_links", 0),
                last_error=stats["error"], success=0 if stats["error"] else 1,
            ))
        db.commit()

        logger.info("Fetched: %d", summary["fetched"])
        logger.info("Filtered: %d", summary["filtered_out"])
        logger.info("Rejected: %d", summary["filtered_out"])
        logger.info("Accepted: %d", accepted_count)
        if accepted_scores:
            logger.info("Average relevance score: %.1f", sum(accepted_scores) / len(accepted_scores))
            logger.info("Highest score: %d", max(accepted_scores))
            logger.info("Lowest accepted score: %d", min(accepted_scores))
        else:
            logger.info("Average relevance score: N/A (no jobs accepted this run)")
            logger.info("Highest score: N/A")
            logger.info("Lowest accepted score: N/A")

        if check_expired:
            try:
                expiry_summary = remove_expired_jobs(db=db)
                summary["expired_removed"] = expiry_summary["removed"]
            except Exception as exc:
                logger.error("Expired-link sweep failed: %s", exc)
                summary["errors"].append(f"link_health: {exc}")

        # --- Telegram notifications ---------------------------------
        # Every job that is genuinely new this run (newly_saved_rows)
        # gets notified, one message per job (never batched), and each
        # is sent (and marked telegram_notified=1) individually so one
        # failure doesn't block the rest and so a re-run of the
        # collector can never resend an already-sent notification.
        if notify and newly_saved_rows:
            for row in newly_saved_rows:
                if row.telegram_notified:
                    continue  # already sent (shouldn't happen for a brand-new row, but stay safe)
                try:
                    telegram.notify_job(row.to_dict())
                    row.telegram_notified = 1
                    db.add(row)
                    db.commit()
                    summary["notified"] += 1
                except Exception as exc:
                    logger.error("Telegram notification failed for job_url=%s: %s", row.job_url, exc)
                    summary["errors"].append(f"telegram: {exc}")
            logger.info("Telegram: %d notification(s) sent.", summary["notified"])

        return summary
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run job collectors")
    parser.add_argument("--query", default=None, help="Single search term (skips the full matrix)")
    parser.add_argument("--location", default=None, help="Single location (used with --query)")
    parser.add_argument("--no-notify", action="store_true", help="Skip Telegram notification")
    parser.add_argument("--skip-expiry-check", action="store_true",
                         help="Skip the end-of-run sweep that removes expired job postings "
                              "(that sweep makes one HTTP request per stored job, so it can be slow on a large DB)")
    args = parser.parse_args()

    run(query=args.query, location=args.location, notify=not args.no_notify,
        check_expired=not args.skip_expiry_check)
