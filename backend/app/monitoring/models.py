"""
New, additive table for collector run monitoring. Separate from
`jobs` (unchanged) -- same Base/engine, same jobs.db file.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.database import Base


class CollectorRun(Base):
    __tablename__ = "collector_runs"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    fetched = Column(Integer, default=0)
    accepted = Column(Integer, default=0)
    rejected = Column(Integer, default=0)
    removed = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    success = Column(Integer, default=1)

    def to_dict(self):
        return {
            "source": self.source,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "fetched": self.fetched, "accepted": self.accepted,
            "rejected": self.rejected, "removed": self.removed,
            "last_error": self.last_error, "success": bool(self.success),
        }
