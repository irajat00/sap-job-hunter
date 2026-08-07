"""
Tests for the V15 extension to GET /jobs: search, sort, page/page_size,
and the ephemeral relevance_score field. Confirms backward
compatibility with the original source/location/limit/offset
interface, and that nothing is persisted to the database.
"""
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Job

client = TestClient(app)


class TestJobsEndpointV15Extensions(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        now = datetime.now(timezone.utc)

        def iso(dt):
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        j1 = Job(title="SAP PP Consultant", company="Accenture", location="Berlin", salary="80000",
                  source="adzuna", job_url="https://x.com/1", posted_date=iso(now - timedelta(days=5)), description="")
        j1.created_at = now - timedelta(hours=3)
        j2 = Job(title="SAP QM Consultant", company="Bosch", location="Dubai", salary=None,
                  source="jooble", job_url="https://x.com/2", posted_date=iso(now - timedelta(days=10)), description="")
        j2.created_at = now - timedelta(hours=2)
        j3 = Job(title="SAP Manufacturing Consultant", company="ACME", location="Remote", salary=None,
                  source="jooble", job_url="https://x.com/3", posted_date=iso(now - timedelta(days=1)), description="")
        j3.created_at = now - timedelta(hours=1)

        db.add_all([j1, j2, j3])
        db.commit()
        db.close()

    def test_backward_compatible_default_response(self):
        r = client.get("/jobs")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(set(data.keys()), {"total", "count", "results"})
        # newest (by created_at) first, matching original default behavior
        self.assertEqual(data["results"][0]["title"], "SAP Manufacturing Consultant")
        # additive field present, original fields untouched
        self.assertIn("relevance_score", data["results"][0])
        for field in ["id", "title", "company", "location", "salary", "source",
                      "job_url", "posted_date", "description", "created_at"]:
            self.assertIn(field, data["results"][0])

    def test_legacy_limit_offset_unaffected(self):
        r = client.get("/jobs?limit=1&offset=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_search_matches_title_company_location(self):
        self.assertEqual(len(client.get("/jobs?search=Bosch").json()["results"]), 1)
        self.assertEqual(len(client.get("/jobs?search=Dubai").json()["results"]), 1)
        self.assertEqual(len(client.get("/jobs?search=SAP QM").json()["results"]), 1)
        self.assertEqual(len(client.get("/jobs?search=nonexistent_xyz").json()["results"]), 0)

    def test_sort_relevance_descending(self):
        scores = [j["relevance_score"] for j in client.get("/jobs?sort=relevance").json()["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_sort_oldest(self):
        r = client.get("/jobs?sort=oldest").json()
        self.assertEqual(r["results"][0]["title"], "SAP PP Consultant")

    def test_sort_company_alphabetical(self):
        companies = [j["company"] for j in client.get("/jobs?sort=company").json()["results"]]
        self.assertEqual(companies, sorted(companies, key=str.lower))

    def test_sort_location_alphabetical(self):
        locations = [j["location"] for j in client.get("/jobs?sort=location").json()["results"]]
        self.assertEqual(locations, sorted(locations, key=str.lower))

    def test_invalid_sort_falls_back_to_newest(self):
        r = client.get("/jobs?sort=not-a-real-option")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["results"][0]["title"], "SAP Manufacturing Consultant")

    def test_page_and_page_size(self):
        r1 = client.get("/jobs?page=1&page_size=2")
        self.assertEqual(r1.json()["count"], 2)
        self.assertEqual(r1.json()["total"], 3)
        r2 = client.get("/jobs?page=2&page_size=2")
        self.assertEqual(r2.json()["count"], 1)

    def test_page_page_size_takes_precedence_over_legacy_params_when_both_given(self):
        r = client.get("/jobs?page=1&page_size=1&limit=100&offset=0")
        self.assertEqual(r.json()["count"], 1)

    def test_relevance_score_never_persisted(self):
        client.get("/jobs?sort=relevance")  # trigger scoring
        db = SessionLocal()
        row = db.query(Job).first()
        self.assertFalse(hasattr(row, "relevance_score"))
        db.close()

    def test_health_unaffected(self):
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
