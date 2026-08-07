import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Job
from app.monitoring.models import CollectorRun
from collectors.resilience import call_with_resilience
from app.ranking import composite_rank
from app.export import export_csv, export_excel, export_pdf

client = TestClient(app)


class TestResilience(unittest.TestCase):
    def test_success_returns_result_no_error(self):
        result, err = call_with_resilience(lambda: [1, 2, 3], source_name="test")
        self.assertEqual(result, [1, 2, 3])
        self.assertIsNone(err)

    def test_failure_retries_then_gives_up(self):
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            raise ValueError("boom")
        result, err = call_with_resilience(flaky, source_name="test")
        self.assertEqual(result, [])
        self.assertIn("boom", err)
        self.assertGreater(calls["n"], 1)  # confirms retries happened


class TestRanking(unittest.TestCase):
    def test_higher_base_score_ranks_higher(self):
        class FakeRow:
            created_at = datetime.now(timezone.utc)
            salary = None
        r1 = composite_rank(FakeRow(), base_score=100)
        r2 = composite_rank(FakeRow(), base_score=50)
        self.assertGreater(r1, r2)

    def test_match_percent_increases_rank(self):
        class FakeRow:
            created_at = datetime.now(timezone.utc)
            salary = None
        base = composite_rank(FakeRow(), base_score=50)
        with_match = composite_rank(FakeRow(), base_score=50, match_percent=90)
        self.assertGreater(with_match, base)


class TestExport(unittest.TestCase):
    def setUp(self):
        self.jobs = [{"title": "SAP PP Consultant", "company": "A", "location": "Berlin",
                      "salary": "80000", "source": "adzuna", "posted_date": "2026-01-01", "job_url": "https://x.com/1"}]

    def test_csv_export(self):
        content = export_csv(self.jobs)
        self.assertIn(b"SAP PP Consultant", content)

    def test_excel_export(self):
        content = export_excel(self.jobs)
        self.assertTrue(content.startswith(b"PK"))  # xlsx is a zip archive

    def test_pdf_export(self):
        content = export_pdf(self.jobs)
        self.assertTrue(content.startswith(b"%PDF"))


class TestDashboardAndCollectorStatus(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        db.add(Job(title="SAP PP Consultant", company="A", location="Dubai", source="adzuna",
                    job_url="https://x.com/1", description=""))
        db.add(CollectorRun(source="adzuna", fetched=10, accepted=3, rejected=7, removed=1, success=1))
        db.commit()
        db.close()

    def test_collector_status_endpoint(self):
        r = client.get("/collector-status")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data[0]["source"], "adzuna")
        self.assertEqual(data[0]["fetched"], 10)

    def test_dashboard_endpoint(self):
        r2 = client.get("/dashboard")
        self.assertEqual(r2.status_code, 200)
        data = r2.json()
        self.assertEqual(set(data.keys()), {"total_jobs", "jobs_today", "latest_jobs"})
        self.assertEqual(data["total_jobs"], 1)

    def test_export_endpoint(self):
        r = client.post("/export?format=csv", json=["https://x.com/1"])
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"SAP PP Consultant", r.content)


if __name__ == "__main__":
    unittest.main()
