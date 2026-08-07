"""
Naukri collector — not implemented yet.

Naukri's terms prohibit unauthorized scraping. Check their
RecruiterConnect / partner API options before implementing this.
"""
from collectors.base import BaseCollector


class NaukriCollector(BaseCollector):
    source_name = "naukri"

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        raise NotImplementedError("Naukri collector not implemented yet.")
