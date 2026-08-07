import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.models import Job

client = TestClient(app)


class TestJobsV17Extensions(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        now = datetime.now(timezone.utc)

        def iso(dt):
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        db.add_all([
            Job(title="SAP PP Consultant", company="Accenture", location="Dubai", salary="80,000",
                source="adzuna", job_url="https://x.com/1", posted_date=iso(now - timedelta(hours=2)), description=""),
            Job(title="SAP QM Consultant", company="Bosch", location="Bangalore", salary=None,
                source="jooble", job_url="https://x.com/2", posted_date=iso(now - timedelta(days=3)), description=""),
            Job(title="SAP PP/QM Consultant", company="Siemens", location="Berlin", salary="95,000",
                source="jooble", job_url="https://x.com/3", posted_date=iso(now - timedelta(days=10)), description=""),
            Job(title="SAP MM Consultant", company="Accenture", location="London", salary=None,
                source="adzuna", job_url="https://x.com/4", posted_date=iso(now - timedelta(days=1)),
                description="Materials management and inventory role."),
            Job(title="SAP PP Consultant", company="Continental", location="Remote", salary="70,000",
                source="jooble", job_url="https://x.com/5", posted_date=iso(now - timedelta(days=40)), description=""),
        ])
        db.commit()
        db.close()

    def test_backward_compatible(self):
        r = client.get("/jobs")
        self.assertEqual(r.json()["total"], 5)

    def test_location_bucket_filter(self):
        r = client.get("/jobs?location_bucket=UAE")
        self.assertEqual(len(r.json()["results"]), 1)
        r2 = client.get("/jobs?location_bucket=India")
        self.assertEqual(len(r2.json()["results"]), 1)

    def test_category_filter(self):
        r = client.get("/jobs?category=SAP PP/QM")
        self.assertEqual(len(r.json()["results"]), 1)
        r3 = client.get("/jobs?category=SAP PP")
        # includes the two plain "SAP PP Consultant" rows plus the
        # "SAP PP/QM Consultant" row (bare PP token also present there)
        self.assertEqual(len(r3.json()["results"]), 3)

    def test_company_filter(self):
        r = client.get("/jobs?company=Accenture")
        self.assertEqual(len(r.json()["results"]), 2)

    def test_salary_filter(self):
        r = client.get("/jobs?salary=available")
        r2 = client.get("/jobs?salary=not_listed")
        self.assertEqual(r.json()["total"] + r2.json()["total"], 5)

    def test_posted_within_filter(self):
        r = client.get("/jobs?posted_within=7")
        self.assertEqual(r.json()["total"], 3)
        r2 = client.get("/jobs?posted_within=today")
        # both the 2-hours-ago and ~1-day-ago rows can fall inside a rolling
        # 24h window depending on exact test execution timing
        self.assertIn(r2.json()["total"], (1, 2))

    def test_relevance_score_still_present(self):
        r = client.get("/jobs")
        self.assertIn("relevance_score", r.json()["results"][0])


class TestJobsFacets(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        now = datetime.now(timezone.utc)

        def iso(dt):
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        db.add_all([
            Job(title="SAP PP Consultant", company="Accenture", location="Dubai", salary="80,000",
                source="adzuna", job_url="https://x.com/1", posted_date=iso(now - timedelta(hours=2)), description=""),
            Job(title="SAP QM Consultant", company="Bosch", location="Bangalore", salary=None,
                source="jooble", job_url="https://x.com/2", posted_date=iso(now - timedelta(days=3)), description=""),
            Job(title="SAP PP/QM Consultant", company="Siemens", location="Berlin", salary="95,000",
                source="jooble", job_url="https://x.com/3", posted_date=iso(now - timedelta(days=10)), description=""),
            Job(title="SAP MM Consultant", company="Accenture", location="London", salary=None,
                source="adzuna", job_url="https://x.com/4", posted_date=iso(now - timedelta(days=1)),
                description="Materials management and inventory role."),
            Job(title="SAP PP Consultant", company="Continental", location="Remote", salary="70,000",
                source="jooble", job_url="https://x.com/5", posted_date=iso(now - timedelta(days=40)), description=""),
        ])
        db.commit()
        db.close()

    def test_response_shape(self):
        r = client.get("/jobs/facets")
        data = r.json()
        self.assertEqual(set(data.keys()), {"locations", "categories", "companies", "stats"})

    def test_location_counts_total(self):
        r = client.get("/jobs/facets")
        all_bucket = [l for l in r.json()["locations"] if l["key"] == "All"][0]
        self.assertEqual(all_bucket["count"], 5)

    def test_location_facet_excludes_its_own_filter(self):
        # Filtering by company=Accenture (Dubai + London rows) should
        # still show location counts reflecting only those two rows,
        # not be additionally constrained by any location selection.
        r = client.get("/jobs/facets?company=Accenture")
        locs = {l["key"]: l["count"] for l in r.json()["locations"]}
        self.assertEqual(locs["UAE"], 1)
        self.assertEqual(locs["UK"], 1)
        self.assertEqual(locs["All"], 2)

    def test_company_facet_excludes_its_own_filter(self):
        r = client.get("/jobs/facets?location_bucket=UAE")
        companies = {c["name"]: c["count"] for c in r.json()["companies"]}
        self.assertEqual(companies.get("Accenture"), 1)

    def test_category_facet_counts(self):
        r = client.get("/jobs/facets")
        cats = {c["key"]: c["count"] for c in r.json()["categories"]}
        self.assertEqual(cats["SAP PP"], 3)  # includes the SAP PP/QM row too (bare PP token present)
        self.assertEqual(cats["SAP QM"], 2)  # includes the SAP PP/QM row too (bare QM token present)
        self.assertEqual(cats["SAP PP/QM"], 1)
        self.assertNotIn("HR / HRBP", cats)
        self.assertEqual(cats["All Jobs"], 5)

    def test_stats_reflect_all_active_filters_together(self):
        r = client.get("/jobs/facets")
        stats = r.json()["stats"]
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["uae"], 1)
        self.assertEqual(stats["india"], 1)
        self.assertEqual(stats["germany"], 1)
        self.assertEqual(stats["remote"], 1)
        self.assertNotIn("hr", stats)
        self.assertEqual(stats["sap"], 4)

    def test_stats_change_with_active_filters(self):
        r = client.get("/jobs/facets?category=SAP QM")
        stats = r.json()["stats"]
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["sap"], 2)


if __name__ == "__main__":
    unittest.main()
