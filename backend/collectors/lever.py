"""
Lever Postings API collector — official, free, public, no auth.

Docs: https://github.com/lever/postings-api (Lever's own repo,
explicitly described as the API "used by external careers pages").

Same shape as greenhouse.py: no server-side keyword search, so this
fetches each configured company's full posting list (cached per run)
and filters locally by query/location. Configure companies via
LEVER_COMPANIES in app/config.py -- empty by default, safe no-op.
"""
import os
import logging
from datetime import datetime, timezone
import requests

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings/{company}?mode=json"


def _epoch_ms_to_iso(value) -> str | None:
    """
    Lever's `createdAt` is epoch milliseconds, not a date string. The
    existing 180-day filter in app/main.py parses posted_date as an
    ISO string, so convert here -- otherwise every Lever job would
    have posted_date=None and silently skip age filtering entirely.
    """
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError, OSError):
        return None


def _default_companies() -> list[str]:
    env_val = os.getenv("LEVER_COMPANIES", "")
    if env_val:
        return [c.strip() for c in env_val.split(",") if c.strip()]
    try:
        from app.config import LEVER_COMPANIES
        return list(LEVER_COMPANIES)
    except ImportError:
        return []


class LeverCollector(BaseCollector):
    source_name = "lever"

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
                for item in data:
                    categories = item.get("categories") or {}
                    jobs.append({
                        "title": (item.get("text") or "").strip(),
                        "company": company,
                        "location": categories.get("location"),
                        "salary": None,  # only present for some postings; skip for consistency
                        "source": self.source_name,
                        "job_url": item.get("hostedUrl"),
                        "posted_date": _epoch_ms_to_iso(item.get("createdAt")),
                        "description": item.get("descriptionPlain") or item.get("description"),
                    })
                self._cache[company] = jobs
            except requests.RequestException as exc:
                logger.warning("[lever] company '%s' failed: %s", company, exc)
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
