"""
Generic RSS/Atom feed collector -- free, no auth, official mechanism
many job boards and company career sites expose deliberately for
subscription (unlike scraping, this is content the publisher chose to
syndicate). Config-driven: point it at any feed URLs and it works,
no per-source code needed.

Configure via RSS_FEED_URLS in .env (comma-separated), empty by
default -- zero requests, zero jobs, until configured.
"""
import os
import logging

import feedparser

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


def _default_feeds() -> list[str]:
    env_val = os.getenv("RSS_FEED_URLS", "")
    return [u.strip() for u in env_val.split(",") if u.strip()]


class RSSFeedCollector(BaseCollector):
    source_name = "rss"

    def __init__(self, feed_urls: list[str] = None):
        self.feed_urls = feed_urls if feed_urls is not None else _default_feeds()

    def fetch_jobs(self, query: str = "", location: str = "") -> list[dict]:
        if not self.feed_urls:
            return []
        jobs = []
        query_lower = (query or "").lower()
        for url in self.feed_urls:
            try:
                parsed = feedparser.parse(url)
            except Exception as exc:
                logger.warning("[rss] feed '%s' failed: %s", url, exc)
                continue
            for entry in parsed.entries:
                title = entry.get("title", "")
                if query_lower and query_lower not in title.lower() and query_lower not in entry.get("summary", "").lower():
                    continue
                jobs.append({
                    "title": title,
                    "company": entry.get("author") or entry.get("source", {}).get("title") if isinstance(entry.get("source"), dict) else None,
                    "location": None,
                    "salary": None,
                    "source": self.source_name,
                    "job_url": entry.get("link"),
                    "posted_date": entry.get("published") or entry.get("updated"),
                    "description": entry.get("summary", ""),
                })
        return jobs
