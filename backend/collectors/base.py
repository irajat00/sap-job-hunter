"""
BaseCollector — the contract every job source implements.

Adding a new source later (LinkedIn, Naukri, Foundit, JSearch, an
official employer API, whatever) means: subclass this, implement
fetch_jobs(), register it in runner.py. Nothing else in the app needs
to change.
"""
from abc import ABC, abstractmethod


class BaseCollector(ABC):
    # Short, stable identifier stored in Job.source — e.g. "adzuna", "naukri".
    source_name: str = "base"

    @abstractmethod
    def fetch_jobs(self, query: str, location: str = "") -> list[dict]:
        """
        Return a list of job postings matching `query` (optionally near
        `location`). Each posting must be a dict shaped like:

            {
                "title": str,
                "company": str | None,
                "location": str | None,
                "salary": str | None,
                "source": str,          # should equal self.source_name
                "job_url": str,         # required — used as the dedup key
                "posted_date": str | None,
                "description": str | None,
            }

        Postings missing "job_url" are skipped by the runner since they
        can't be deduplicated.
        """
        raise NotImplementedError
