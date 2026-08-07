"""
Every job source is a subclass of collectors.base.BaseCollector,
implementing:

    fetch_jobs(self, query: str, location: str = "") -> list[dict]

...returning dicts shaped like:

    {
        "title": str,
        "company": str | None,
        "location": str | None,
        "salary": str | None,
        "source": str,          # should match the collector's source_name
        "job_url": str,         # required -- used as the dedup key
        "posted_date": str | None,
        "description": str | None,
    }

To add a new source:
    1. Create collectors/<name>.py with a class SomeCollector(BaseCollector)
    2. Set source_name and implement fetch_jobs()
    3. Register an instance of it in runner.py's COLLECTORS list

Nothing else in the app (models, runner logic, API) needs to change.
"""
