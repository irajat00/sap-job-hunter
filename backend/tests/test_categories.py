import unittest

from app.categories import matches_category, ALL_CATEGORIES


def job(title="", description=""):
    return {"title": title, "description": description}


class TestPlainCategories(unittest.TestCase):
    def test_sap_pp(self):
        self.assertTrue(matches_category(job(title="SAP PP Consultant"), "SAP PP"))
        self.assertTrue(matches_category(job(title="PPDS Scheduler"), "SAP PP"))
        self.assertFalse(matches_category(job(title="SAP QM Consultant"), "SAP PP"))

    def test_sap_qm(self):
        self.assertTrue(matches_category(job(title="SAP QM Consultant"), "SAP QM"))
        self.assertTrue(matches_category(job(title="Quality Management Lead"), "SAP QM"))
        self.assertFalse(matches_category(job(title="SAP PP Consultant"), "SAP QM"))


class TestCompositeCategory(unittest.TestCase):
    def test_pp_qm_requires_both(self):
        self.assertTrue(matches_category(job(title="SAP PP/QM Consultant"), "SAP PP/QM"))
        self.assertFalse(matches_category(job(title="SAP PP Consultant"), "SAP PP/QM"))
        self.assertFalse(matches_category(job(title="SAP QM Consultant"), "SAP PP/QM"))


class TestAllJobsAndDefaults(unittest.TestCase):
    def test_all_jobs_matches_everything(self):
        self.assertTrue(matches_category(job(title="Anything"), "All Jobs"))
        self.assertTrue(matches_category(job(title=""), "All Jobs"))

    def test_falsy_category_matches_everything(self):
        self.assertTrue(matches_category(job(title="Anything"), None))
        self.assertTrue(matches_category(job(title="Anything"), ""))

    def test_unrecognized_category_matches_nothing(self):
        self.assertFalse(matches_category(job(title="SAP PP Consultant"), "Not A Real Category"))

    def test_all_categories_list_contains_expected_entries(self):
        self.assertIn("All Jobs", ALL_CATEGORIES)
        self.assertIn("SAP PP", ALL_CATEGORIES)
        self.assertIn("SAP QM", ALL_CATEGORIES)
        self.assertIn("SAP PP/QM", ALL_CATEGORIES)
        self.assertNotIn("HR / HRBP", ALL_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
