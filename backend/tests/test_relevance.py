"""
Unit tests for app/relevance.py (V14: internal 0-100 relevance scoring,
used only to decide keep/reject -- score itself is never persisted or
returned by the API).

Run with:
    python -m unittest tests.test_relevance -v
or:
    python -m unittest discover tests
"""
import unittest

from app.relevance import (
    is_relevant,
    filter_relevant,
    score_job,
    _is_relevant_ppqm,
    ACCEPTANCE_THRESHOLD,
)


def job(title="", description=""):
    return {"title": title, "description": description}


class TestScoringBands(unittest.TestCase):
    """Exact score-band examples from the spec."""

    def test_exact_titles_score_100(self):
        for title in ["SAP PP Consultant", "SAP QM Consultant", "SAP PP/QM Consultant"]:
            with self.subTest(title=title):
                self.assertEqual(score_job(job(title=title)), 100)

    def test_very_strong_titles_score_95_to_99(self):
        titles = [
            "SAP Production Planning Consultant",
            "SAP S/4HANA PP Consultant",
            "SAP PP Lead",
            "SAP PPDS Consultant",
        ]
        for title in titles:
            with self.subTest(title=title):
                score = score_job(job(title=title))
                self.assertTrue(95 <= score <= 99, f"{title!r} scored {score}, expected 95-99")

    def test_good_band_with_strong_description_scores_85_to_94(self):
        strong_description = (
            "Responsible for SAP PP configuration and customizing, including rollout support "
            "for production planning processes."
        )
        for title in ["SAP Functional Consultant", "Consultant", "Senior Consultant"]:
            with self.subTest(title=title):
                score = score_job(job(title=title, description=strong_description))
                self.assertTrue(85 <= score <= 94, f"{title!r} scored {score}, expected 85-94")

    def test_weak_titles_score_60_to_84_with_no_description(self):
        for title in ["SAP Manufacturing Consultant", "SAP Planning Consultant"]:
            with self.subTest(title=title):
                score = score_job(job(title=title, description=""))
                self.assertTrue(60 <= score <= 84, f"{title!r} scored {score}, expected 60-84")

    def test_below_60_is_rejected(self):
        self.assertLess(score_job(job(title="Senior Liquidity Risk Manager")), 60)
        self.assertFalse(_is_relevant_ppqm(job(title="Senior Liquidity Risk Manager")))


class TestDescriptionBonus(unittest.TestCase):
    """More implementation-activity keywords -> higher score, within the band ceiling."""

    def test_bonus_increases_score_up_to_band_ceiling(self):
        title = "SAP PPDS Consultant"  # very-strong band, base 95, ceiling 99
        no_bonus_score = score_job(job(title=title, description=""))
        with_bonus_score = score_job(job(
            title=title,
            description="Includes configuration, customizing, rollout, testing, and MRP activities.",
        ))
        self.assertEqual(no_bonus_score, 95)
        self.assertGreater(with_bonus_score, no_bonus_score)
        self.assertLessEqual(with_bonus_score, 99)  # never exceeds the band ceiling

    def test_bonus_never_pushes_past_100_for_exact_titles(self):
        j = job(
            title="SAP PP Consultant",
            description="Configuration, customizing, implementation, rollout, testing, MRP, routing.",
        )
        self.assertEqual(score_job(j), 100)  # already at ceiling, bonus is a no-op


class TestDescriptionPenalty(unittest.TestCase):
    """Generic/unrelated keywords in the description reduce score heavily,
    potentially below the acceptance threshold."""

    def test_penalty_reduces_weak_band_score(self):
        title = "SAP Manufacturing Consultant"  # weak band, base 65
        clean_score = score_job(job(title=title, description=""))
        penalized_score = score_job(job(
            title=title,
            description="This role also covers procurement, warehouse, and logistics topics.",
        ))
        self.assertLess(penalized_score, clean_score)

    def test_heavy_penalty_pushes_weak_job_below_threshold(self):
        j = job(
            title="SAP Manufacturing Consultant",
            description="Primarily a procurement, warehouse, logistics, and inventory role with SAP exposure.",
        )
        score = score_job(j)
        self.assertLess(score, ACCEPTANCE_THRESHOLD)
        self.assertFalse(_is_relevant_ppqm(j))

    def test_heavy_penalty_can_reject_a_good_band_job_despite_passing_evidence_check(self):
        j = job(
            title="SAP Functional Consultant",
            description=(
                "SAP PP configuration and rollout, but role is mostly procurement, warehouse, "
                "logistics, inventory, and finance coordination."
            ),
        )
        score = score_job(j)
        self.assertLess(score, ACCEPTANCE_THRESHOLD)
        self.assertFalse(_is_relevant_ppqm(j))


class TestHardRejectAlwaysScoresZero(unittest.TestCase):
    def test_reject_list_titles_score_zero_regardless_of_description(self):
        cases = [
            ("NPI Buyer", "Strong SAP PP/QM background, configuration and rollout experience required."),
            ("SAP APO Consultant", ""),
            ("SAP APO PPDS Consultant", ""),
            ("Software Engineer", "Builds SAP-integrated production planning tools using MRP data."),
        ]
        for title, description in cases:
            with self.subTest(title=title):
                self.assertEqual(score_job(job(title=title, description=description)), 0)


class TestPPDSVsApoPpds(unittest.TestCase):
    def test_plain_ppds_accepted(self):
        self.assertTrue(_is_relevant_ppqm(job(title="SAP PPDS Consultant")))

    def test_apo_ppds_rejected(self):
        self.assertFalse(_is_relevant_ppqm(job(title="SAP APO PPDS Consultant")))


class TestAmbiguousTitleRequiresBothEvidenceGroups(unittest.TestCase):
    def test_only_group_a_present_scores_zero(self):
        j = job(title="SAP Consultant", description="Focus on production planning and quality management topics.")
        self.assertEqual(score_job(j), 0)

    def test_only_group_b_present_scores_zero(self):
        j = job(title="SAP Consultant", description="Leading rollout, configuration, and testing activities.")
        self.assertEqual(score_job(j), 0)

    def test_neither_group_present_scores_zero(self):
        j = job(title="SAP Consultant", description="Great opportunity to grow your consulting career.")
        self.assertEqual(score_job(j), 0)


class TestScoreNeverAttachedToJobDict(unittest.TestCase):
    """The core V14 constraint: score is computed but never stored on
    the job dict, the database, or the API response."""

    def test_filter_relevant_does_not_mutate_or_add_fields_to_kept_jobs(self):
        original = job(title="SAP PP Consultant", description="")
        kept, dropped = filter_relevant([original])
        self.assertEqual(len(kept), 1)
        self.assertEqual(set(kept[0].keys()), {"title", "description"})
        self.assertNotIn("relevance_score", kept[0])
        self.assertNotIn("score", kept[0])


class TestSuffixAgnosticFallbackPreserved(unittest.TestCase):
    """Regression test: V11-V13 all treated 'SAP PP'/'SAP QM' as
    positive regardless of suffix (Analyst, Support, Specialist, ...).
    The V14 banded scoring system must not silently lose that -- these
    should score well (very-strong band) even though they're not one
    of the 3 literal 'exact' Consultant-suffix phrases."""

    def test_various_suffixes_still_accepted(self):
        titles = [
            "SAP QM Analyst",
            "SAP PP Support",
            "SAP PP/QM Specialist",
            "SAP MM/PP Integration Consultant",
        ]
        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(is_relevant(job(title=title)), f"{title!r} should still be accepted")


class TestFilterRelevantBatchInterface(unittest.TestCase):
    def test_returns_tuple_of_kept_list_and_dropped_count(self):
        jobs = [
            job(title="SAP PP Consultant"),
            job(title="SAP IBP Consultant"),
            job(title="Software Engineer"),
            job(title="SAP QM Analyst"),
        ]
        kept, dropped = filter_relevant(jobs)
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, 2)
        self.assertEqual([j["title"] for j in kept], ["SAP PP Consultant", "SAP QM Analyst"])

    def test_empty_list(self):
        kept, dropped = filter_relevant([])
        self.assertEqual(kept, [])
        self.assertEqual(dropped, 0)


class TestProfileDispatchStillWorks(unittest.TestCase):
    def test_is_relevant_uses_scoring_for_ppqm(self):
        self.assertTrue(is_relevant(job(title="SAP PP Consultant")))
        self.assertFalse(is_relevant(job(title="SAP IBP Consultant")))


if __name__ == "__main__":
    unittest.main()
