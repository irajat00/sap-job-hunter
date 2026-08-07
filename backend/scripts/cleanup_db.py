"""
One-time (or as-needed) database cleanup: re-scores every existing row
in jobs.db using the CURRENT, unmodified score_job() and
ACCEPTANCE_THRESHOLD from app/relevance.py, and removes rows that fall
below that threshold.

Why this exists: relevance filtering only ever runs once, at
insertion time, inside collectors/runner.py. A row saved under an
earlier, more permissive version of the relevance filter is never
retroactively re-evaluated by the normal collector pipeline, and
GET /jobs never applies a relevance floor to what it already has
stored -- it only uses score_job() for sorting/display. This script is
the one-time remedy for that accumulated historical data; it does not
change how the collector or the API behave going forward, and it does
not modify score_job(), is_relevant(), the collector pipeline,
duplicate detection, or the database schema in any way -- it only
deletes rows via their existing `id` column, exactly like any other
row deletion.

Safety: defaults to a DRY RUN. The four required counts (total rows,
rows below threshold, rows that will be deleted, rows that will
remain) are always printed BEFORE anything is deleted. Nothing is
actually removed unless --execute is passed.

Usage:
    python -m scripts.cleanup_db              # dry run (default) -- prints impact only, deletes nothing
    python -m scripts.cleanup_db --execute     # prints the same impact, THEN deletes
"""
import argparse

from app.database import SessionLocal
from app.models import Job
from app.relevance import score_job, ACCEPTANCE_THRESHOLD


def analyze(db) -> dict:
    """
    Re-scores every row using the CURRENT score_job(), unmodified.
    Does not delete anything -- read-only. Returns:
        {"total": int, "below_threshold_ids": [row ids scoring < ACCEPTANCE_THRESHOLD]}
    """
    all_jobs = db.query(Job).all()
    below_threshold_ids = [
        row.id for row in all_jobs
        if score_job({"title": row.title, "description": row.description}) < ACCEPTANCE_THRESHOLD
    ]
    return {"total": len(all_jobs), "below_threshold_ids": below_threshold_ids}


def run_cleanup(execute: bool = False, db=None) -> dict:
    """
    Prints the four required counts, then deletes rows below the
    current threshold ONLY if execute=True. Returns a summary dict:
        {"total": int, "below_threshold": int, "deleted": int, "remaining": int}
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()

    try:
        result = analyze(db)
        total = result["total"]
        below_ids = result["below_threshold_ids"]
        below_count = len(below_ids)
        remaining_count = total - below_count

        print(f"Total rows before cleanup: {total}")
        print(f"Rows below threshold (score < {ACCEPTANCE_THRESHOLD}): {below_count}")
        print(f"Rows that will be deleted: {below_count}")
        print(f"Rows remaining after cleanup: {remaining_count}")

        if not execute:
            print()
            print("DRY RUN -- no rows deleted. Re-run with --execute to actually delete them.")
            return {"total": total, "below_threshold": below_count, "deleted": 0, "remaining": total}

        if below_ids:
            db.query(Job).filter(Job.id.in_(below_ids)).delete(synchronize_session=False)
            db.commit()

        print()
        print(f"Deleted {below_count} rows. {remaining_count} rows remain.")
        return {"total": total, "below_threshold": below_count, "deleted": below_count, "remaining": remaining_count}
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="One-time cleanup: remove rows scoring below the current relevance threshold"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually delete rows. Default is a dry run that only prints the impact.",
    )
    args = parser.parse_args()

    run_cleanup(execute=args.execute)
