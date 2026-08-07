"""
Greenhouse Job Board API collector — official, free, public, no auth.

Docs: https://developers.greenhouse.io/job-board.html
Confirmed directly from Greenhouse's own docs: "Job Board data is
publicly available, so authentication is not required for any GET
endpoints." This is the same feed Greenhouse customers use to power
their own public career pages.

Unlike Adzuna/Jooble, this API has no keyword search -- it returns ALL
of a company's open jobs, namespaced by a "board token" (the slug in
that company's boards.greenhouse.io/<token> URL). So this collector:
    1. Fetches each configured company's full job list (once per run,
       cached in memory -- see note below)
    2. Filters locally by whether `query` appears in the title/content
       and whether `location` appears in the job's location string

Configure companies via GREENHOUSE_COMPANIES in app/config.py (empty by
default -- see that file and the README for how to find real board
tokens). With no companies configured, this collector makes zero
requests and returns zero jobs -- a safe no-op.

Why the cache: collectors/runner.py calls fetch_jobs() once per
(keyword, location) combination -- 72 times in a full run. Without
caching, that would mean 72 identical HTTP requests per company
fetching the exact same job list. Caching at the instance level (reset
each time a new collector instance is created, i.e. each time
`python -m collectors.runner` runs) avoids that entirely without
requiring any change to runner.py's loop structure.
"""
import os
import logging
import requests

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true"


def _default_companies() -> list[str]:
    env_val = os.getenv("GREENHOUSE_COMPANIES", "")
    if env_val:
        return [c.strip() for c in env_val.split(",") if c.strip()]
    try:
        from app.config import GREENHOUSE_COMPANIES
        return list(GREENHOUSE_COMPANIES)
    except ImportError:
        return []


class GreenhouseCollector(BaseCollector):
    source_name = "greenhouse"

    def __init__(self, companies: list[str] = None):
        self.companies = companies if companies is not None else _default_companies()
        self._cache: dict[str, list[dict]] = {}
        self._fetched = False

    def _fetch_all_companies(self) -> None:
        for company in self.companies:
            try:
                resp = requests.get(BASE_URL.format(company=company), timeout=15)
                resp.raise_for_status()
                data = resp.json()
                jobs = []
                for item in data.get("jobs", []):
                    jobs.append({
                        "title": (item.get("title") or "").strip(),
                        "company": company,
                        "location": (item.get("location") or {}).get("name"),
                        "salary": None,  # Greenhouse's public feed doesn't expose salary
                        "source": self.source_name,
                        "job_url": item.get("absolute_url"),
                        "posted_date": item.get("updated_at"),
                        "description": item.get("content"),
                    })
                self._cache[company] = jobs
            except requests.RequestException as exc:
                logger.warning("[greenhouse] company '%s' failed: %s", company, exc)
                self._cache[company] = []
        self._fetched = True

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        if not self.companies:
            return []
        if not self._fetched:
            self._fetch_all_companies()

        query_lower = query.lower()
        location_lower = location.lower() if location else None

        results = []
        for company_jobs in self._cache.values():
            for job in company_jobs:
                haystack = f"{job.get('title') or ''} {job.get('description') or ''}".lower()
                if query_lower and query_lower not in haystack:
                    continue
                if location_lower and location_lower not in (job.get("location") or "").lower():
                    continue
                results.append(job)
        return results
