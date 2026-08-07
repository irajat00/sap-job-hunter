"""
Jooble collector — a free, official job-search aggregator API.

Jooble's REST API (see https://jooble.org/api/about) is free for
developers: you register for an API key at no cost, and there's no
per-call charge (Jooble's revenue model is referral clicks on their own
site, not API fees). It's a genuine second keyword+location-searchable
aggregator alongside Adzuna, covering dozens of countries.

Setup:
    1. Request a free API key at https://jooble.org/api/about
    2. Set env var JOOBLE_API_KEY

Note: I could not verify from Jooble's public documentation whether UAE
is among its covered countries (their own materials confirm Germany,
India, and most of Europe/North America, but don't give a definitive
country list). This collector doesn't assume either way -- a query
against an uncovered region should just come back with zero results
rather than erroring, so nothing breaks either way.

Pagination: Jooble's API returns one page of results per call (a
"page" parameter in the request body) plus a totalCount telling you how
many results exist in total. This collector walks forward through pages
until it has them all, or hits MAX_PAGES -- a safety cap so one keyword/
location combo can't spin into an unbounded number of requests.
"""
import os
import logging
import requests

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY", "")
BASE_URL = "https://jooble.org/api/{key}"

# Safety cap on pages fetched per (keyword, location) combo. With the
# default 12 keywords x 6 locations = 72 combos per run, raising this
# multiplies total API calls proportionally -- keep an eye on whatever
# rate limit your free Jooble account actually has if you increase it.
MAX_PAGES = 3


class JoobleCollector(BaseCollector):
    source_name = "jooble"

    def __init__(self, api_key: str = None, max_pages: int = None):
        self.api_key = api_key or JOOBLE_API_KEY
        self.max_pages = max_pages if max_pages is not None else MAX_PAGES

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        if not self.api_key:
            raise RuntimeError(
                "Missing JOOBLE_API_KEY. Get a free key at https://jooble.org/api/about"
            )

        url = BASE_URL.format(key=self.api_key)
        jobs = []
        page = 1

        while page <= self.max_pages:
            payload = {"keywords": query, "page": str(page)}
            if location:
                payload["location"] = location

            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            page_jobs = data.get("jobs", [])
            if not page_jobs:
                break  # no more results, stop paging

            for item in page_jobs:
                jobs.append({
                    "title": (item.get("title") or "").strip(),
                    "company": item.get("company"),
                    "location": item.get("location"),
                    "salary": item.get("salary") or None,
                    "source": self.source_name,
                    "job_url": item.get("link"),
                    "posted_date": item.get("updated"),
                    "description": item.get("snippet"),
                })

            total_count = data.get("totalCount", 0)
            if len(jobs) >= total_count:
                break  # fetched everything Jooble has for this query

            page += 1

        return jobs
