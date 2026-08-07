"""
Tests for the Telegram-notification pipeline (now the primary feature,
no resume/profile involved):

  - notifiers/telegram.py: exact message format, credentials read from
    the environment only.
  - collectors/runner.py: every newly-saved job gets an immediate,
    individual Telegram notification, and re-running the collector
    never resends a notification for a job it already sent one for.
"""
import os
import unittest
from unittest.mock import patch, MagicMock

from app.database import Base, engine, SessionLocal
from app.models import Job
from notifiers import telegram
import collectors.runner as runner
from collectors.base import BaseCollector


class FakeCollector(BaseCollector):
    source_name = "jooble"

    def __init__(self, jobs_by_call):
        self._jobs_by_call = jobs_by_call
        self._call_index = 0

    def fetch_jobs(self, query: str, location: str = "") -> list[dict]:
        jobs = self._jobs_by_call[self._call_index] if self._call_index < len(self._jobs_by_call) else []
        self._call_index += 1
        return jobs


JOB_A = {
    "title": "SAP PP Consultant",
    "company": "Bosch",
    "location": "Berlin, Germany",
    "salary": None,
    "source": "jooble",
    "job_url": "https://jooble.example/job-a",
    "posted_date": "2026-07-01",
    "description": "SAP PP configuration and rollout.",
}

JOB_B = {
    "title": "SAP QM Consultant",
    "company": "Siemens",
    "location": "Remote",
    "salary": None,
    "source": "jooble",
    "job_url": "https://jooble.example/job-b",
    "posted_date": "2026-07-02",
    "description": "SAP QM support role.",
}


class TestTelegramFormat(unittest.TestCase):
    def test_format_job_message_matches_required_layout(self):
        job = {
            "title": "SAP PP Consultant",
            "company": "Bosch",
            "location": "Berlin, Germany",
            "posted_date": "2026-07-01",
            "job_url": "https://example.com/job/1",
        }
        message = telegram.format_job_message(job)
        expected = (
            "🚨 New SAP Job Found!\n\n"
            "Title:\n"
            "SAP PP Consultant\n"
            "Company:\n"
            "Bosch\n"
            "Location:\n"
            "Berlin, Germany\n"
            "Posted:\n"
            "2026-07-01\n\n"
            "Open Job:\n"
            "https://example.com/job/1"
        )
        self.assertEqual(message, expected)

    def test_missing_credentials_raises_clear_error(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            with self.assertRaises(RuntimeError):
                telegram.notify_job(JOB_A)

    def test_notify_job_posts_formatted_text(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "12345"}):
            fake_response = MagicMock()
            fake_response.raise_for_status = MagicMock()
            with patch("notifiers.telegram.requests.post", return_value=fake_response) as mock_post:
                result = telegram.notify_job(JOB_A)
        self.assertTrue(result)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["chat_id"], "12345")
        self.assertIn("🚨 New SAP Job Found!", kwargs["json"]["text"])
        self.assertNotIn("Resume Match", kwargs["json"]["text"])


class TestRunnerNotifiesEveryNewJobOnce(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
        os.environ["TELEGRAM_CHAT_ID"] = "12345"

    def _run_with_fake_collector(self, jobs_by_call, notified_jobs):
        fake_collector = FakeCollector(jobs_by_call)
        with patch.object(runner, "COLLECTORS", [fake_collector]), \
             patch("collectors.runner.time.sleep"), \
             patch("collectors.self_maintain.run_self_maintenance", return_value={"removed_dead_links": 0}), \
             patch.object(runner.telegram, "notify_job", side_effect=lambda job: notified_jobs.append(job["job_url"]) or True):
            return runner.run(query="SAP PP", location="Germany", notify=True, check_expired=False)

    def test_every_new_job_saved_and_notified_once(self):
        notified = []
        summary = self._run_with_fake_collector([[JOB_A, JOB_B]], notified)

        self.assertEqual(summary["saved"], 2)
        self.assertEqual(summary["notified"], 2)
        self.assertEqual(set(notified), {JOB_A["job_url"], JOB_B["job_url"]})

        db = SessionLocal()
        for url in (JOB_A["job_url"], JOB_B["job_url"]):
            row = db.query(Job).filter(Job.job_url == url).first()
            self.assertIsNotNone(row)
            self.assertEqual(row.telegram_notified, 1)
        db.close()

    def test_rerunning_collector_never_resends_notification(self):
        notified = []
        summary1 = self._run_with_fake_collector([[JOB_A]], notified)
        self.assertEqual(summary1["notified"], 1)

        summary2 = self._run_with_fake_collector([[JOB_A]], notified)
        self.assertEqual(summary2["saved"], 0)
        self.assertEqual(summary2["duplicates"], 1)
        self.assertEqual(summary2["notified"], 0)
        self.assertEqual(notified, [JOB_A["job_url"]])  # still only sent once total

        db = SessionLocal()
        row = db.query(Job).filter(Job.job_url == JOB_A["job_url"]).first()
        self.assertEqual(row.telegram_notified, 1)
        db.close()

    def test_no_batching_one_message_per_job(self):
        notified = []
        self._run_with_fake_collector([[JOB_A, JOB_B]], notified)
        # One notify_job call per job -- never one combined/batched call.
        self.assertEqual(len(notified), 2)


if __name__ == "__main__":
    unittest.main()
