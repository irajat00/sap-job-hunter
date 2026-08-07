"""
Sends ONE daily Telegram summary of job-collection activity. Run once a
day by .github/workflows/daily-summary.yml (0 21 * * *, i.e. 9 PM --
see that file to change the time/timezone). Does not run as part of
the regular 5-minute collector workflow.

Entirely additive: reuses the existing Job model and the existing
notifiers/telegram.py credential/send mechanism via the new
send_daily_summary() function added there -- collectors/runner.py, the
per-job instant notification path (notify_job/format_job_message), and
every existing endpoint/test are untouched.

Usage:
    python -m scripts.daily_summary
"""
import app.env  # noqa: F401  (loads .env as an import side effect)
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Job
from notifiers.telegram import send_daily_summary


def build_stats(db) -> dict:
    """
    "Today" = a rolling 24-hour window ending now (same convention
    already used by the dashboard's jobs_today figure), not a
    calendar-day boundary -- this avoids any timezone ambiguity between
    the collector's run times and this summary's.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    all_rows = db.query(Job).all()

    def created_within_last_day(row) -> bool:
        if not row.created_at:
            return False
        c = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
        return c >= cutoff

    new_today = [r for r in all_rows if created_within_last_day(r)]
    notified_today = [r for r in new_today if r.telegram_notified]

    return {
        "date": now.strftime("%Y-%m-%d"),
        "new_today": len(new_today),
        "notified_today": len(notified_today),
        "total_jobs": len(all_rows),
    }


def main():
    db = SessionLocal()
    try:
        stats = build_stats(db)
        send_daily_summary(stats)
        print(f"Daily summary sent: {stats}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
