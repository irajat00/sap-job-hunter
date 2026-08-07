"""
Unit tests for collectors/link_health.py.

Uses mocked HTTP responses throughout -- this project's dev sandbox has
no general internet access, and even in a real deployment we shouldn't
depend on hitting live external job boards in a unit test.
"""
import unittest
from unittest.mock import patch, MagicMock

from app.database import Base, engine, SessionLocal
from app.models import Job
from collectors.link_health import remove_expired_jobs, _looks_expired


def _make_response(status_code=200, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


class TestLooksExpired(unittest.TestCase):
    def test_404_is_expired(self):
        self.assertTrue(_looks_expired(_make_response(status_code=404)))

    def test_410_is_expired(self):
        self.assertTrue(_looks_expired(_make_response(status_code=410)))

    def test_200_with_expiry_text_is_expired(self):
        for phrase in ["Job no longer available", "POSITION NO LONGER AVAILABLE", "This vacancy has expired"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(_looks_expired(_make_response(status_code=200, text=f"<html>{phrase}</html>")))

    def test_200_with_normal_content_is_not_expired(self):
        self.assertFalse(_looks_expired(_make_response(status_code=200, text="<html>SAP PP Consultant role...</html>")))

    def test_other_status_codes_not_expired(self):
        self.assertFalse(_looks_expired(_make_response(status_code=500)))
        self.assertFalse(_looks_expired(_make_response(status_code=301)))


class TestRemoveExpiredJobs(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.add_all([
            Job(title="SAP PP Consultant", company="A", location="Berlin", source="adzuna",
                job_url="https://example.com/still-live", description=""),
            Job(title="SAP QM Consultant", company="B", location="Munich", source="jooble",
                job_url="https://example.com/gone-404", description=""),
            Job(title="SAP PPDS Consultant", company="C", location="Stuttgart", source="jooble",
                job_url="https://example.com/expired-text", description=""),
            Job(title="SAP PP Lead", company="D", location="Remote", source="adzuna",
                job_url="https://example.com/network-error", description=""),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_removes_404_and_expiry_text_but_keeps_live_and_error_rows(self):
        import requests

        def fake_get(url, timeout=None, allow_redirects=None):
            if url == "https://example.com/still-live":
                return _make_response(status_code=200, text="Great SAP PP role, apply now.")
            if url == "https://example.com/gone-404":
                return _make_response(status_code=404)
            if url == "https://example.com/expired-text":
                return _make_response(status_code=200, text="This vacancy has expired.")
            if url == "https://example.com/network-error":
                raise requests.RequestException("connection timed out")
            raise AssertionError(f"unexpected url: {url}")

        with patch("collectors.link_health.requests.get", side_effect=fake_get):
            summary = remove_expired_jobs(db=self.db)

        self.assertEqual(summary["checked"], 4)
        self.assertEqual(summary["removed"], 2)
        self.assertEqual(summary["errors"], 1)

        remaining_urls = {row.job_url for row in self.db.query(Job).all()}
        self.assertEqual(remaining_urls, {"https://example.com/still-live", "https://example.com/network-error"})

    def test_empty_database_is_a_no_op(self):
        self.db.query(Job).delete()
        self.db.commit()
        with patch("collectors.link_health.requests.get") as mock_get:
            summary = remove_expired_jobs(db=self.db)
        self.assertEqual(summary, {"checked": 0, "removed": 0, "errors": 0})
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
