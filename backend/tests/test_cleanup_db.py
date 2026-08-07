"""
Tests for scripts/cleanup_db.py.

Confirms: dry-run deletes nothing, execute deletes exactly the rows
scoring below the current ACCEPTANCE_THRESHOLD (using the real,
unmodified score_job()), the four printed/returned counts are
correct, and running it twice is idempotent.
"""
import unittest

from app.database import Base, engine, SessionLocal
from app.models import Job
from app.relevance import score_job, ACCEPTANCE_THRESHOLD
from scripts.cleanup_db import analyze, run_cleanup


class TestCleanupDb(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        # A deliberate mix: some rows that clearly score >= 60 today
        # (genuine SAP PP/QM titles) and some that clearly score < 60
        # (the kind of historical row an earlier, looser filter version
        # would have accepted but the current score_job() would not).
        self.db.add_all([
            Job(title="SAP PP Consultant", company="A", location="Berlin", source="adzuna",
                job_url="https://x.com/keep1", description=""),
            Job(title="SAP QM Consultant", company="B", location="Munich", source="jooble",
                job_url="https://x.com/keep2", description=""),
            Job(title="SAP PPDS Consultant", company="C", location="Remote", source="jooble",
                job_url="https://x.com/keep3", description=""),
            Job(title="Senior Liquidity Risk Manager", company="D", location="Frankfurt", source="jooble",
                job_url="https://x.com/drop1", description=""),
            Job(title="Procurement Specialist", company="E", location="Hamburg", source="adzuna",
                job_url="https://x.com/drop2", description=""),
        ])
        self.db.commit()

        # Sanity-check my own fixture against the real score_job(), so
        # this test can't silently drift from whatever the current
        # scoring logic actually does.
        titles_and_expected = {
            "SAP PP Consultant": True,
            "SAP QM Consultant": True,
            "SAP PPDS Consultant": True,
            "Senior Liquidity Risk Manager": False,
            "Procurement Specialist": False,
        }
        for title, expected_kept in titles_and_expected.items():
            score = score_job({"title": title, "description": ""})
            is_kept = score >= ACCEPTANCE_THRESHOLD
            assert is_kept == expected_kept, (
                f"Test fixture assumption invalid: {title!r} scored {score}, "
                f"expected kept={expected_kept}. Adjust the fixture, not score_job()."
            )

    def tearDown(self):
        self.db.close()

    def test_analyze_identifies_correct_rows_without_deleting(self):
        result = analyze(self.db)
        self.assertEqual(result["total"], 5)
        self.assertEqual(len(result["below_threshold_ids"]), 2)

        # Nothing deleted -- analyze() is read-only.
        remaining = self.db.query(Job).count()
        self.assertEqual(remaining, 5)

    def test_dry_run_deletes_nothing(self):
        summary = run_cleanup(execute=False, db=self.db)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["below_threshold"], 2)
        self.assertEqual(summary["deleted"], 0)
        self.assertEqual(summary["remaining"], 5)  # dry run -- nothing actually removed

        remaining = self.db.query(Job).count()
        self.assertEqual(remaining, 5, "dry run must not delete any rows")

    def test_execute_deletes_exactly_the_below_threshold_rows(self):
        summary = run_cleanup(execute=True, db=self.db)
        self.assertEqual(summary["total"], 5)
        self.assertEqual(summary["below_threshold"], 2)
        self.assertEqual(summary["deleted"], 2)
        self.assertEqual(summary["remaining"], 3)

        remaining_titles = {row.title for row in self.db.query(Job).all()}
        self.assertEqual(remaining_titles, {"SAP PP Consultant", "SAP QM Consultant", "SAP PPDS Consultant"})

    def test_idempotent_second_run_finds_nothing_left_to_delete(self):
        run_cleanup(execute=True, db=self.db)
        second_summary = run_cleanup(execute=True, db=self.db)
        self.assertEqual(second_summary["total"], 3)
        self.assertEqual(second_summary["below_threshold"], 0)
        self.assertEqual(second_summary["deleted"], 0)
        self.assertEqual(second_summary["remaining"], 3)

    def test_empty_database_is_a_no_op(self):
        self.db.query(Job).delete()
        self.db.commit()
        summary = run_cleanup(execute=True, db=self.db)
        self.assertEqual(summary, {"total": 0, "below_threshold": 0, "deleted": 0, "remaining": 0})


if __name__ == "__main__":
    unittest.main()
