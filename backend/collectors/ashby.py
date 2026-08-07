"""
Ashby Job Postings API collector — official, free, public, no auth.

Docs: https://developers.ashbyhq.com/docs/public-job-posting-api

Same shape as greenhouse.py/lever.py: no server-side keyword search, so
this fetches each configured company's full posting list (cached per
run) and filters locally by query/location. Configure companies via
ASHBY_COMPANIES in app/config.py -- empty by default, safe no-op.

Ashby's feed does include an explicit isRemote/workplaceType flag per
posting (unlike Greenhouse/Lever, which only have free-text location
strings) -- a genuinely more precise remote-role signal if you
configure companies here.
"""
import os
import logging
import requests

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{company}"


def _default_companies() -> list[str]:
    env_val = os.getenv("ASHBY_COMPANIES", "")
    if env_val:
        return [c.strip() for c in env_val.split(",") if c.strip()]
    try:
        from app.config import ASHBY_COMPANIES
        return list(ASHBY_COMPANIES)
    except ImportError:
        return []


class AshbyCollector(BaseCollector):
    source_name = "ashby"

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
                    location = item.get("location")
                    if item.get("isRemote") and location:
                        location = f"{location} (Remote)"
                    elif item.get("isRemote"):
                        location = "Remote"
                    jobs.append({
                        "title": (item.get("title") or "").strip(),
                        "company": company,
                        "location": location,
                        "salary": None,  # only present when includeCompensation=true and the org opts in
                        "source": self.source_name,
                        "job_url": item.get("jobUrl") or item.get("applyUrl"),
                        "posted_date": item.get("publishedAt"),
                        "description": item.get("descriptionPlain") or item.get("descriptionHtml"),
                    })
                self._cache[company] = jobs
            except requests.RequestException as exc:
                logger.warning("[ashby] company '%s' failed: %s", company, exc)
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
