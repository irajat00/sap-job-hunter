"""
Exports the current jobs table to a static JSON file the frontend can
fetch directly, with no live backend involved.

Why this exists: the free, zero-cost deployment (GitHub Actions +
GitHub Pages) has no way to run a persistently-listening FastAPI
server for the frontend to call -- GitHub Pages only serves static
files. This script is the bridge: it runs the SAME, UNMODIFIED
classification functions the API uses (app/locations.normalize_location,
app/categories.matches_category, app/relevance.score_job) against every
job in the database and writes the result as one static JSON file that
frontend/src/api.js reads instead of calling GET /jobs / GET
/jobs/facets over HTTP. This keeps the frontend's filtering, sorting,
and faceting behavior equivalent to the original live-backend version
without touching collectors/runner.py, notifiers/telegram.py, or any
existing API endpoint.

Usage:
    python -m scripts.export_jobs_json
    JOBS_JSON_OUTPUT=/custom/path.json python -m scripts.export_jobs_json

Called automatically by .github/workflows/collect-jobs.yml and
.github/workflows/daily-summary.yml after each collector run.
"""
import json
import os

import app.env  # noqa: F401  (loads .env as an import side effect)
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Job
from app.locations import normalize_location, BUCKET_ORDER
from app.categories import matches_category, ALL_CATEGORIES
from app.relevance import score_job

# Default path lands in the frontend's public/ dir, so Vite copies it
# into the build output verbatim and it's served at /data/jobs.json
# (or /<repo-name>/data/jobs.json under a GitHub Pages project site,
# via Vite's BASE_URL -- see frontend/src/api.js).
DEFAULT_OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "public", "data", "jobs.json"
)


def _max_age_days() -> int:
    raw = os.getenv("JOB_MAX_AGE_DAYS", "90")
    try:
        return int(raw)
    except ValueError:
        return 90


def build_export(output_path: str = None) -> int:
    output_path = output_path or os.getenv("JOBS_JSON_OUTPUT", DEFAULT_OUTPUT_PATH)
    db = SessionLocal()
    try:
        rows = db.query(Job).order_by(Job.created_at.desc()).all()
        jobs = []
        for row in rows:
            job_for_classification = {"title": row.title, "description": row.description}
            d = row.to_dict()
            # Precomputed fields so the static frontend never needs to
            # reimplement the regex-based category/location logic --
            # it only needs to compare these values, using the exact
            # same functions app/main.py's live endpoints call.
            d["location_bucket"] = normalize_location(row.location)
            d["categories"] = [
                cat for cat in ALL_CATEGORIES
                if cat != "All Jobs" and matches_category(job_for_classification, cat)
            ]
            d["relevance_score"] = score_job(job_for_classification)
            jobs.append(d)

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "all_categories": ALL_CATEGORIES,
            "bucket_order": BUCKET_ORDER,
            "job_max_age_days": _max_age_days(),
            "jobs": jobs,
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(payload, f, separators=(",", ":"))  # compact -- this file is fetched by browsers

        print(f"Exported {len(jobs)} jobs to {output_path}")
        return len(jobs)
    finally:
        db.close()


if __name__ == "__main__":
    build_export()
