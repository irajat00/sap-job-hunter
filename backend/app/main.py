"""
FastAPI app — exposes GET /jobs and GET /jobs/facets.

Run with:
    uvicorn app.main:app --reload
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.env  # noqa: F401  (loads .env as an import side effect)
from app.database import get_db
from app.models import Job
from app.relevance import score_job  # reused as-is, never modified -- see note on GET /jobs below
from app.locations import normalize_location, BUCKET_ORDER
from app.categories import matches_category, ALL_CATEGORIES

app = FastAPI(title="SAP PP/QM Job Collector API")

# Needed so a browser-based frontend (e.g. the Vite dev server on
# localhost:5173) is allowed to call this API on localhost:8000 --
# without this, browsers block the request entirely regardless of what
# the frontend code does. Restricted to local dev origins; widen this
# list if you deploy the frontend somewhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _max_age_days() -> int:
    raw = os.getenv("JOB_MAX_AGE_DAYS", "90")
    try:
        return int(raw)
    except ValueError:
        return 90  # bad value in the env -- fall back rather than crash


def _parse_posted_date(value: Optional[str]):
    """
    posted_date is stored as a plain string, and different collectors
    may format it differently. Returns a timezone-aware datetime if it
    parses, else None. None is treated as "unknown age" and never
    excludes a job -- same as an actually-missing posted_date.
    """
    if not value:
        return None
    try:
        # Handles "...Z" (UTC) suffixes as well as offset-included ISO strings.
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


SORT_OPTIONS = {"newest", "oldest", "relevance", "company", "location"}
SALARY_OPTIONS = {"any", "available", "not_listed"}
POSTED_WITHIN_OPTIONS = {"today", "7", "30", "90"}


def _age_cutoff(days: int):
    # posted_date strings only carry second-level precision, so truncate
    # microseconds too -- otherwise a job posted exactly `days` ago
    # loses a microsecond race against "now" and gets excluded when it
    # shouldn't be. Same technique as the existing JOB_MAX_AGE_DAYS filter.
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0)


def _is_recent_enough(row: Job, cutoff) -> bool:
    posted = _parse_posted_date(row.posted_date)
    if posted is None:
        return True  # null/missing/unparseable posted_date is never excluded
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return posted >= cutoff


def _matches_salary(row: Job, salary_filter: Optional[str]) -> bool:
    if not salary_filter or salary_filter == "any":
        return True
    has_salary = bool(row.salary and row.salary.strip())
    if salary_filter == "available":
        return has_salary
    if salary_filter == "not_listed":
        return not has_salary
    return True  # unrecognized value -> no-op, don't exclude anything


def _matches_posted_within(row: Job, posted_within: Optional[str]) -> bool:
    if not posted_within:
        return True
    days_map = {"today": 1, "7": 7, "30": 30, "90": 90}
    days = days_map.get(posted_within)
    if days is None:
        return True  # unrecognized value -> no-op
    posted = _parse_posted_date(row.posted_date)
    if posted is None:
        return False  # unlike the overall age filter, an explicit "posted within X" request
                       # should not include jobs of unknown age -- the two filters serve
                       # different purposes (one is a floor to keep the DB relevant, this
                       # one is a precise user-chosen window)
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return posted >= _age_cutoff(days)


def _load_base_rows(db: Session, source: Optional[str] = None) -> list[Job]:
    """
    Fetches every row matching the optional exact `source` filter (the
    only filter still cheap to push into SQL) plus the standing
    JOB_MAX_AGE_DAYS floor, ordered newest-first. Everything else
    (search, category, company, location bucket, salary, posted_within,
    sort, pagination) is applied in Python afterward -- same
    established pattern as the original age-filter, appropriate at
    this dataset's size (see the V16 root-cause note in app/main.py's
    git history / prior investigation for why this stays a Python-side
    filter rather than a schema change).
    """
    q = db.query(Job)
    if source:
        q = q.filter(Job.source == source)
    all_rows = q.order_by(Job.created_at.desc()).all()

    cutoff = _age_cutoff(_max_age_days())
    return [row for row in all_rows if _is_recent_enough(row, cutoff)]


def _matches_search(row: Job, search: Optional[str]) -> bool:
    if not search:
        return True
    s = search.strip().lower()
    if not s:
        return True
    from app.synonyms import expand_search_terms
    terms = expand_search_terms(s)
    haystack = " ".join(filter(None, [row.title, row.company, row.location, row.description])).lower()
    return any(t in haystack for t in terms)


def _apply_common_filters(
    rows: list[Job],
    search: Optional[str] = None,
    category: Optional[str] = None,
    company: Optional[str] = None,
    location_bucket: Optional[str] = None,
    salary: Optional[str] = None,
    posted_within: Optional[str] = None,
) -> list[Job]:
    """Applies every filter except `source` (already applied in _load_base_rows)."""
    result = rows
    if search:
        result = [r for r in result if _matches_search(r, search)]
    if category and category != "All Jobs":
        result = [r for r in result if matches_category({"title": r.title, "description": r.description}, category)]
    if company:
        c = company.strip().lower()
        result = [r for r in result if (r.company or "").strip().lower() == c]
    if location_bucket and location_bucket != "All":
        result = [r for r in result if normalize_location(r.location) == location_bucket]
    if salary:
        result = [r for r in result if _matches_salary(r, salary)]
    if posted_within:
        result = [r for r in result if _matches_posted_within(r, posted_within)]
    return result


@app.get("/jobs")
def list_jobs(
    source: Optional[str] = Query(None, description="Filter by source, e.g. 'jooble'"),
    location: Optional[str] = Query(None, description="Filter by location substring (legacy, exact substring match)"),
    location_bucket: Optional[str] = Query(None, alias="location_bucket",
                                            description="Filter by normalized location bucket: UAE|India|Germany|UK|Remote|Other"),
    category: Optional[str] = Query(None, description="Filter by job category, e.g. 'SAP PP'. See /jobs/facets for the full list."),
    company: Optional[str] = Query(None, description="Filter by exact company name"),
    salary: Optional[str] = Query(None, description="any (default) | available | not_listed"),
    posted_within: Optional[str] = Query(None, description="today | 7 | 30 | 90 (days)"),
    search: Optional[str] = Query(None, description="Search across title, company, location, and description"),
    sort: Optional[str] = Query("newest", description="newest (default) | oldest | relevance | company | location"),
    limit: int = Query(100, le=500),
    offset: int = 0,
    page: Optional[int] = Query(None, ge=1, description="1-indexed page number; overrides limit/offset if given with page_size"),
    page_size: Optional[int] = Query(None, ge=1, le=500, description="Results per page; overrides limit/offset if given with page"),
    db: Session = Depends(get_db),
):
    """
    Backward compatible: source, location, search, sort, limit, offset,
    page, page_size all behave exactly as in V15 if the new params
    (location_bucket, category, company, salary, posted_within) are
    omitted. Every new param is purely additive.

    Relevance scoring note: score_job() (app/relevance.py, UNCHANGED)
    is called here fresh per request, purely to support sort=relevance
    and the relevance_score field in each result. The score is never
    written back to the database.
    """
    base_rows = _load_base_rows(db, source=source)

    # `location` (legacy substring filter) and `location_bucket` (new,
    # normalized) are independent and can combine -- but ordinarily
    # you'd use one or the other.
    filtered = base_rows
    if location:
        loc = location.lower()
        filtered = [r for r in filtered if loc in (r.location or "").lower()]
    filtered = _apply_common_filters(
        filtered, search=search, category=category, company=company,
        location_bucket=location_bucket, salary=salary, posted_within=posted_within,
    )

    # Ephemeral score per row -- computed fresh, never persisted. Paired
    # with each row for sorting; attached to the response dict below.
    scored_rows = [(row, score_job({"title": row.title, "description": row.description})) for row in filtered]

    sort_key = (sort or "newest").strip().lower()
    if sort_key not in SORT_OPTIONS:
        sort_key = "newest"  # unrecognized value -> safe default rather than erroring

    if sort_key == "oldest":
        scored_rows.sort(key=lambda pair: pair[0].created_at or datetime.min)
    elif sort_key == "relevance":
        scored_rows.sort(key=lambda pair: pair[1], reverse=True)
    elif sort_key == "company":
        scored_rows.sort(key=lambda pair: (pair[0].company or "").lower())
    elif sort_key == "location":
        scored_rows.sort(key=lambda pair: (pair[0].location or "").lower())
    else:  # "newest" (default) -- reaffirm explicitly; already the DB query's order, but sort is
           # applied post-search-filter too, so this keeps behavior correct and explicit either way.
        scored_rows.sort(key=lambda pair: pair[0].created_at or datetime.min, reverse=True)

    total = len(scored_rows)

    # page/page_size (new) takes precedence over limit/offset (original)
    # when both are given; otherwise limit/offset behaves exactly as before.
    if page is not None and page_size is not None:
        eff_offset = (page - 1) * page_size
        eff_limit = page_size
    else:
        eff_offset = offset
        eff_limit = limit

    page_rows = scored_rows[eff_offset:eff_offset + eff_limit]

    results = []
    for row, score in page_rows:
        d = row.to_dict()
        d["relevance_score"] = score  # additive only -- every original field is still present
        results.append(d)

    return {
        "total": total,
        "count": len(results),
        "results": results,
    }


@app.get("/jobs/facets")
def jobs_facets(
    source: Optional[str] = Query(None),
    location_bucket: Optional[str] = Query(None, alias="location_bucket"),
    category: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    salary: Optional[str] = Query(None),
    posted_within: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    New endpoint (additive -- does not change GET /jobs's existing
    behavior or fields). Returns everything the sidebar and dashboard
    stats need in one call, computed from the same JOB_MAX_AGE_DAYS
    floor as /jobs:

        {
          "locations": [{"key": "All", "count": N}, {"key": "UAE", "count": N}, ...],
          "categories": [{"key": "All Jobs", "count": N}, {"key": "SAP PP", "count": N}, ...],
          "companies": [{"name": "Accenture", "count": N}, ...],   # top 100 by count, desc
          "stats": {"total": N, "new_today": N, "remote": N, "uae": N,
                     "india": N, "germany": N, "sap": N}
        }

    Proper faceted-search semantics: each facet's counts are computed
    with every OTHER active filter applied, but not its own dimension
    -- so switching the location filter shows how many jobs are in
    each location bucket given the current category/company/salary/
    posted_within/search selections, without the current location
    selection itself constraining those counts. `stats`, by contrast,
    reflects ALL currently active filters together (it's a summary of
    "what you're looking at right now", not a facet picker).
    """
    base_rows = _load_base_rows(db, source=source)

    def with_all_except(exclude: str) -> list[Job]:
        kwargs = dict(search=search, category=category, company=company,
                      location_bucket=location_bucket, salary=salary, posted_within=posted_within)
        kwargs[exclude] = None
        return _apply_common_filters(base_rows, **kwargs)

    # --- Locations facet (excludes its own filter) ---
    rows_for_location_counts = with_all_except("location_bucket")
    location_counts = {bucket: 0 for bucket in BUCKET_ORDER}
    for row in rows_for_location_counts:
        location_counts["All"] += 1
        location_counts[normalize_location(row.location)] += 1
    locations = [{"key": bucket, "count": location_counts[bucket]} for bucket in BUCKET_ORDER]

    # --- Categories facet (excludes its own filter) ---
    rows_for_category_counts = with_all_except("category")
    categories = []
    for cat in ALL_CATEGORIES:
        count = sum(
            1 for row in rows_for_category_counts
            if matches_category({"title": row.title, "description": row.description}, cat)
        )
        categories.append({"key": cat, "count": count})

    # --- Companies facet (excludes its own filter) ---
    rows_for_company_counts = with_all_except("company")
    company_tally: dict[str, int] = {}
    for row in rows_for_company_counts:
        name = (row.company or "").strip()
        if not name:
            continue
        company_tally[name] = company_tally.get(name, 0) + 1
    companies = [
        {"name": name, "count": count}
        for name, count in sorted(company_tally.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    ][:100]

    # --- Dashboard stats: ALL active filters applied together ---
    rows_for_stats = _apply_common_filters(
        base_rows, search=search, category=category, company=company,
        location_bucket=location_bucket, salary=salary, posted_within=posted_within,
    )
    today_cutoff = _age_cutoff(1)

    def is_new_today(row: Job) -> bool:
        posted = _parse_posted_date(row.posted_date)
        if posted is None:
            return False
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        return posted >= today_cutoff

    stats = {
        "total": len(rows_for_stats),
        "new_today": sum(1 for r in rows_for_stats if is_new_today(r)),
        "remote": sum(1 for r in rows_for_stats if normalize_location(r.location) == "Remote"),
        "uae": sum(1 for r in rows_for_stats if normalize_location(r.location) == "UAE"),
        "india": sum(1 for r in rows_for_stats if normalize_location(r.location) == "India"),
        "germany": sum(1 for r in rows_for_stats if normalize_location(r.location) == "Germany"),
        "sap": sum(
            1 for r in rows_for_stats
            if matches_category({"title": r.title, "description": r.description}, "SAP PP")
            or matches_category({"title": r.title, "description": r.description}, "SAP QM")
        ),
    }

    return {
        "locations": locations,
        "categories": categories,
        "companies": companies,
        "stats": stats,
    }


from fastapi import HTTPException
from app.monitoring.models import CollectorRun
from fastapi.responses import StreamingResponse
from app.export import EXPORTERS
import io


@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """
    Single fixed-user dashboard: Total Jobs, Jobs Today, Latest Jobs only.
    """
    all_rows = db.query(Job).all()
    now = datetime.now(timezone.utc)

    def created_within(row, days):
        if not row.created_at:
            return False
        c = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
        return (now - c).days < days

    jobs_today = sum(1 for r in all_rows if created_within(r, 1))

    latest_rows = sorted(all_rows, key=lambda r: r.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:10]
    latest_jobs = [row.to_dict() for row in latest_rows]

    return {
        "total_jobs": len(all_rows),
        "jobs_today": jobs_today,
        "latest_jobs": latest_jobs,
    }


@app.get("/collector-status")
def collector_status(db: Session = Depends(get_db)):
    sources = [r[0] for r in db.query(CollectorRun.source).distinct().all()]
    result = []
    for src in sources:
        latest = db.query(CollectorRun).filter(CollectorRun.source == src).order_by(CollectorRun.finished_at.desc()).first()
        if latest:
            result.append(latest.to_dict())
    return result


@app.post("/export")
def export_jobs(job_urls: list[str], format: str = "csv", db: Session = Depends(get_db)):
    if format not in EXPORTERS:
        raise HTTPException(400, "format must be csv|excel|pdf")
    rows = db.query(Job).filter(Job.job_url.in_(job_urls)).all()
    jobs = [r.to_dict() for r in rows]
    content = EXPORTERS[format](jobs)
    media_types = {"csv": "text/csv", "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}
    ext = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}[format]
    return StreamingResponse(
        io.BytesIO(content), media_type=media_types[format],
        headers={"Content-Disposition": f"attachment; filename=bookmarked_jobs.{ext}"},
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.query(Job).limit(1).all()
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unreachable"}
