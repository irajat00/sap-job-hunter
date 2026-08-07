"""
SmartRecruiters Posting API collector — official, free, public GET
endpoints, no auth required for reads.

Docs: https://developers.smartrecruiters.com/docs/endpoints

Same shape as greenhouse.py/lever.py/ashby.py: the list endpoint
returns summaries for ALL of a company's postings (no server-side
keyword search), so this fetches and caches each configured company's
list once per run and filters locally by query/location. Configure
companies via SMARTRECRUITERS_COMPANIES in app/config.py -- empty by
default, safe no-op.

Note: the list endpoint doesn't include the full description text, so
keyword matching here is limited to the job title and any short
description snippet the summary includes. If SmartRecruiters is your
main source of new jobs, expect somewhat coarser query matching than
the other ATS collectors.
"""
import os
import logging
import requests

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{company}/postings"


def _default_companies() -> list[str]:
    env_val = os.getenv("SMARTRECRUITERS_COMPANIES", "")
    if env_val:
        return [c.strip() for c in env_val.split(",") if c.strip()]
    try:
        from app.config import SMARTRECRUITERS_COMPANIES
        return list(SMARTRECRUITERS_COMPANIES)
    except ImportError:
        return []


class SmartRecruitersCollector(BaseCollector):
    source_name = "smartrecruiters"

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
                for item in data.get("content", []):
                    location = (item.get("location") or {}).get("city") or (item.get("location") or {}).get("country")
                    jobs.append({
                        "title": (item.get("name") or "").strip(),
                        "company": company,
                        "location": location,
                        "salary": None,
                        "source": self.source_name,
                        "job_url": (item.get("ref") or {}).get("jobAd") or item.get("applyUrl"),
                        "posted_date": item.get("releasedDate") or item.get("createdOn"),
                        "description": (item.get("jobAd") or {}).get("sections", {}).get("jobDescription", {}).get("text"),
                    })
                self._cache[company] = jobs
            except requests.RequestException as exc:
                logger.warning("[smartrecruiters] company '%s' failed: %s", company, exc)
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
