"""
Foundit (formerly Monster India) collector — not implemented yet.

Check for an employer/partner API or RSS feed before implementing this
against foundit.in directly.
"""
from collectors.base import BaseCollector


class FounditCollector(BaseCollector):
    source_name = "foundit"

    def fetch_jobs(self, query: str = "SAP PP QM", location: str = "") -> list[dict]:
        raise NotImplementedError("Foundit collector not implemented yet.")
