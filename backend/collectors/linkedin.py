"""
LinkedIn collector — not implemented yet.

LinkedIn's terms prohibit scraping and they enforce this aggressively
(see hiQ v. LinkedIn). When ready, implement this against LinkedIn's
official Talent Solutions / Jobs API (requires partner access) rather
than scraping linkedin.com directly.
"""
from collectors.base import BaseCollector


class LinkedInCollector(BaseCollector):
    source_name = "linkedin"

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        raise NotImplementedError(
            "LinkedIn collector not implemented. Use LinkedIn's official "
            "Talent/Jobs API (partner access required) rather than scraping."
        )
