"""
Job model — one row per unique job posting.

Deduplication note: `job_url` is unique+indexed. The runner uses this to
decide whether a fetched posting is already known before inserting it,
so re-running a collector never creates duplicate rows.

`telegram_notified` supports the Telegram-notification flow
(collectors/runner.py + notifiers/telegram.py): it's flipped to 1 the
moment a Telegram message is successfully sent for that job so
re-running the collector -- or retrying after a partial failure --
can never send a duplicate notification for the same job.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255))
    location = Column(String(255))
    salary = Column(String(120))
    source = Column(String(50), nullable=False, index=True)   # e.g. "indeed", "naukri"
    job_url = Column(String(1000), nullable=False, unique=True, index=True)
    posted_date = Column(String(100))   # kept as raw string; sources format this differently
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 1 once a Telegram notification has been successfully sent for this
    # job, 0 otherwise. This is the persisted guard behind requirement 7
    # (duplicate protection) -- independent of the in-memory
    # "newly saved this run" check, so it also protects against a crash
    # or restart mid-run.
    telegram_notified = Column(Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "salary": self.salary,
            "source": self.source,
            "job_url": self.job_url,
            "posted_date": self.posted_date,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "telegram_notified": bool(self.telegram_notified),
        }
