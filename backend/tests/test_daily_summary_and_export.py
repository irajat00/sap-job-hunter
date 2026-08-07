"""
Tests for the additive GitHub Actions deployment support:
  - notifiers/telegram.py's new send_daily_summary()/format_daily_summary_message()
  - scripts/daily_summary.py's build_stats()
  - scripts/export_jobs_json.py's build_export()
None of these touch the existing per-job notification path, the
collector, or any existing endpoint.
"""
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from app.database import Base, engine, SessionLocal
from app.models import Job
from notifiers import telegram
from scripts.daily_summary import build_stats
from scripts.export_jobs_json import build_export


class TestDailySummaryFormat(unittest.TestCase):
    def test_format_daily_summary_message(self):
        stats = {"date": "2026-07-28", "new_today": 5, "notified_today": 3, "total_jobs": 120}
        msg = telegram.format_daily_summary_message(stats)
        expected = (
            "📊 Daily SAP Job Summary\n\n"
            "Date: 2026-07-28\n"
            "New jobs found today: 5\n"
            "Notifications sent today: 3\n"
            "Total jobs in database: 120"
        )
        self.assertEqual(msg, expected)

    def test_send_daily_summary_posts_message(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}):
            fake_response = MagicMock()
            fake_response.raise_for_status = MagicMock()
            with patch("notifiers.telegram.requests.post", return_value=fake_response) as mock_post:
                result = telegram.send_daily_summary({"date": "x", "new_today": 0, "notified_today": 0, "total_jobs": 0})
        self.assertTrue(result)
        mock_post.assert_called_once()


class TestBuildStats(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_build_stats_counts_last_24h_and_notified(self):
        db = SessionLocal()
        now = datetime.now(timezone.utc)
        recent = Job(title="SAP PP Consultant", company="A", location="Berlin", source="jooble",
                     job_url="https://x.com/1", created_at=now - timedelta(hours=2), telegram_notified=1)
        recent_not_notified = Job(title="SAP QM Consultant", company="B", location="Remote", source="jooble",
                                   job_url="https://x.com/2", created_at=now - timedelta(hours=5), telegram_notified=0)
        old = Job(title="SAP PP Consultant", company="C", location="Munich", source="adzuna",
                  job_url="https://x.com/3", created_at=now - timedelta(days=3), telegram_notified=1)
        db.add_all([recent, recent_not_notified, old])
        db.commit()

        stats = build_stats(db)
        self.assertEqual(stats["new_today"], 2)
        self.assertEqual(stats["notified_today"], 1)
        self.assertEqual(stats["total_jobs"], 3)
        db.close()


class TestExportJobsJson(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_export_writes_expected_shape(self):
        db = SessionLocal()
        db.add(Job(title="SAP PP Consultant", company="Bosch", location="Berlin, Germany",
                    source="jooble", job_url="https://x.com/export-1",
                    description="SAP PP and SAP QM configuration.", posted_date="2026-07-20"))
        db.commit()
        db.close()

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "jobs.json")
            count = build_export(output_path=out_path)
            self.assertEqual(count, 1)
            with open(out_path) as f:
                payload = json.load(f)

        self.assertIn("jobs", payload)
        self.assertIn("all_categories", payload)
        self.assertIn("bucket_order", payload)
        self.assertEqual(len(payload["jobs"]), 1)
        job = payload["jobs"][0]
        self.assertEqual(job["location_bucket"], "Germany")
        self.assertIn("SAP PP", job["categories"])
        self.assertIn("SAP QM", job["categories"])
        self.assertIn("SAP PP/QM", job["categories"])
        self.assertIn("relevance_score", job)


if __name__ == "__main__":
    unittest.main()
