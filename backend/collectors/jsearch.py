"""
JSearch (RapidAPI) collector — not implemented yet.

JSearch aggregates listings from Indeed/LinkedIn/Glassdoor/etc. under
its own licensed API (via RapidAPI), similar in spirit to Adzuna but
with different coverage. Worth adding as a second aggregator once
Adzuna's coverage for your target roles/regions is proven insufficient.

Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""
from collectors.base import BaseCollector


class JSearchCollector(BaseCollector):
    source_name = "jsearch"

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        raise NotImplementedError("JSearch collector not implemented yet.")
