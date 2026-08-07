"""
Tests confirming the two configuration values that must be settable
purely via .env, with no Python code changes, actually work that way:
SEARCH_KEYWORDS (app/config.py) and JOB_MAX_AGE_DAYS (app/main.py).

These import fresh each time via importlib.reload, since app.config
and the relevant part of app.main read os.environ at import/call time.
"""
import importlib
import os
import unittest


class TestSearchKeywordsFromEnv(unittest.TestCase):
    def setUp(self):
        self._original = os.environ.get("SEARCH_KEYWORDS")

    def tearDown(self):
        if self._original is None:
            os.environ.pop("SEARCH_KEYWORDS", None)
        else:
            os.environ["SEARCH_KEYWORDS"] = self._original

    def test_search_keywords_env_overrides_default_list(self):
        os.environ["SEARCH_KEYWORDS"] = "SAP PP,SAP QM,HR,HRBP,Talent Acquisition"
        import app.config as config
        importlib.reload(config)
        self.assertEqual(
            config.KEYWORDS,
            ["SAP PP", "SAP QM", "HR", "HRBP", "Talent Acquisition"],
        )

    def test_default_keywords_used_when_env_unset(self):
        os.environ.pop("SEARCH_KEYWORDS", None)
        import app.config as config
        importlib.reload(config)
        self.assertIn("SAP PP", config.KEYWORDS)
        self.assertIn("SAP QM", config.KEYWORDS)
        self.assertIn("SAP PP/QM", config.KEYWORDS)
        self.assertIn("SAP Production Planning", config.KEYWORDS)
        self.assertIn("SAP Manufacturing", config.KEYWORDS)
        self.assertIn("SAP APO PPDS", config.KEYWORDS)
        self.assertIn("SAP S/4HANA PP", config.KEYWORDS)
        self.assertIn("SAP S/4HANA Manufacturing", config.KEYWORDS)
        self.assertIn("SAP Digital Manufacturing", config.KEYWORDS)

    def test_default_keyword_list_has_no_extraneous_entries(self):
        # Single fixed-user app: the default keyword list is exactly the
        # required SAP Manufacturing set -- no HR keywords.
        os.environ.pop("SEARCH_KEYWORDS", None)
        import app.config as config
        importlib.reload(config)
        self.assertEqual(len(config.KEYWORDS), 9)


class TestJobMaxAgeDaysFromEnv(unittest.TestCase):
    def setUp(self):
        self._original = os.environ.get("JOB_MAX_AGE_DAYS")

    def tearDown(self):
        if self._original is None:
            os.environ.pop("JOB_MAX_AGE_DAYS", None)
        else:
            os.environ["JOB_MAX_AGE_DAYS"] = self._original

    def test_default_is_90_when_env_unset(self):
        os.environ.pop("JOB_MAX_AGE_DAYS", None)
        from app.main import _max_age_days
        self.assertEqual(_max_age_days(), 90)

    def test_env_override_is_respected(self):
        os.environ["JOB_MAX_AGE_DAYS"] = "30"
        from app.main import _max_age_days
        self.assertEqual(_max_age_days(), 30)

    def test_invalid_env_value_falls_back_to_90(self):
        os.environ["JOB_MAX_AGE_DAYS"] = "not-a-number"
        from app.main import _max_age_days
        self.assertEqual(_max_age_days(), 90)


if __name__ == "__main__":
    unittest.main()
