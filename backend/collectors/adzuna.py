"""
Adzuna collector — a licensed job-search aggregator API.

This is NOT Indeed. It's a separate aggregator (developer.adzuna.com)
that includes some Indeed-sourced listings among others, under Adzuna's
own API terms. Labeled honestly as its own source so nothing downstream
has to guess where a row actually came from.

Adzuna's API is per-country, so fetch_jobs() queries every country in
ADZUNA_COUNTRIES and merges the results, deduplicating by job_url (the
same posting can occasionally surface under more than one country
endpoint).

Setup:
    1. Free app_id + app_key at https://developer.adzuna.com/
    2. Set env vars ADZUNA_APP_ID, ADZUNA_APP_KEY, and ADZUNA_COUNTRIES
       (comma-separated country codes, e.g. "gb,ae,de,in,ca,au")
"""
import os
import logging
import app.env  # noqa: F401  (loads .env as an import side effect, before env vars are read in __init__ below)
import requests

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

DEFAULT_COUNTRIES = ["gb", "us", "de", "fr", "in", "ca", "au", "nz", "za",
                     "pl", "nl", "it", "es", "at", "be", "br", "mx", "sg", "ch"]


class AdzunaCollector(BaseCollector):
    source_name = "adzuna"

    def __init__(self, app_id: str = None, app_key: str = None, countries: list[str] = None):
        self.app_id = app_id or os.getenv("ADZUNA_APP_ID", "")
        self.app_key = app_key or os.getenv("ADZUNA_APP_KEY", "")

        if countries:
            self.countries = countries
        else:
            env_countries = os.getenv("ADZUNA_COUNTRIES", "")
            self.countries = (
                [c.strip().lower() for c in env_countries.split(",") if c.strip()]
                if env_countries else DEFAULT_COUNTRIES
            )

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        if not self.app_id or not self.app_key:
            raise RuntimeError(
                "Missing ADZUNA_APP_ID / ADZUNA_APP_KEY. "
                "Get free credentials at https://developer.adzuna.com/"
            )

        seen_urls = set()
        jobs = []

        for country in self.countries:
            try:
                country_jobs = self._fetch_country(query, location, country)
            except requests.HTTPError as exc:
                # A bad/unsupported country code shouldn't kill the whole
                # collector run -- skip it and keep going with the rest.
                logger.warning("[adzuna] country '%s' failed: %s", country, exc)
                continue

            for job in country_jobs:
                url = job.get("job_url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                jobs.append(job)

        return jobs

    def _fetch_country(self, query: str, location: str, country: str) -> list[dict]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": query,
            "results_per_page": 50,
            "content-type": "application/json",
        }
        if location:
            params["where"] = location

        url = BASE_URL.format(country=country)
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        jobs = []
        for item in payload.get("results", []):
            jobs.append({
                "title": (item.get("title") or "").strip(),
                "company": (item.get("company") or {}).get("display_name"),
                "location": (item.get("location") or {}).get("display_name"),
                "salary": self._format_salary(item),
                "source": self.source_name,
                "job_url": item.get("redirect_url"),
                "posted_date": item.get("created"),
                "description": item.get("description"),
            })
        return jobs

    @staticmethod
    def _format_salary(item: dict) -> str | None:
        lo, hi = item.get("salary_min"), item.get("salary_max")
        if not lo and not hi:
            return None
        if lo and hi and lo != hi:
            return f"{lo:,.0f} - {hi:,.0f}"
        return f"{(lo or hi):,.0f}"
