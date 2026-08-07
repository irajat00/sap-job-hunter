"""
Relevance filter — keeps job search results limited to genuinely
relevant roles, behaving like an experienced SAP recruiter who cares
about QUALITY, not just keyword matches. Runs on already-fetched job
dicts before they're saved to the database; does not touch collector
fetch logic, dedup, the API, the database schema, or the frontend.

V14 introduces an internal 0-100 relevance SCORE used only to make a
better keep/reject decision (accept if score >= 60). The score itself
is NEVER persisted to the database and NEVER returned by the API --
it's computed fresh each time purely to decide is_relevant(), then
discarded. (collectors/runner.py optionally recomputes it again,
separately, purely for an in-memory run summary -- see that file.)

Single-profile app: this file applies one ruleset only -- SAP PP/QM
consultant roles, scored (see "PPQM scoring bands" below). There is no
HR ruleset and no PROFILE env var to switch between rulesets anymore.

=== PPQM scoring bands ===
    0    Hard-reject title (unrelated SAP module or generic
         supply-chain/procurement/logistics/sales/finance/engineering/
         IT role word -- e.g. "NPI Buyer", "SAP APO Consultant") -- a
         hard veto, never rescued by description. Also 0 for any title
         that matches none of the bands below (reject-by-default).
    100  Exact core title: "SAP PP Consultant", "SAP QM Consultant", or
         "SAP PP/QM Consultant" (allowing minor whitespace/case
         variation, but not extra words).
    95-99  Very strong: "SAP Production Planning Consultant", "SAP
         S/4HANA PP Consultant", "SAP PP Lead", "SAP PPDS Consultant".
         Base 95, nudged up toward 99 by implementation-activity
         evidence in the description (see bonus below).
    85-94  Good: an ambiguous role-word title (Consultant, Senior/Lead/
         Principal/Functional Consultant) WITH a strong PP/QM +
         implementation description (both evidence groups present).
         Base 85, nudged up toward 94 by extra evidence.
    60-84  Weak: vague-but-SAP-adjacent titles like "SAP Manufacturing
         Consultant" or "SAP Planning Consultant" that don't name PP or
         QM specifically. Base 65, adjusted by bonus/penalty within
         this band.
    <60  Rejected. Notably, heavy description PENALTY (see below) can
         push a "good" or "weak" band job below 60 even though its
         title looked plausible -- "these jobs should naturally fall
         below the acceptance threshold" when the actual content is
         generic.

Description bonus: +2 per unique implementation-activity keyword found
(Configuration, Customizing, Implementation, Rollout, Support,
Enhancement, Blueprint, Testing, MRP, Production Order, Routing,
Inspection Lot, Batch Management, Master Data, S/4HANA, ECC), capped so
it never pushes a score past that band's ceiling.

Description penalty: -10 per unique generic/unrelated keyword found
(Sales, Presales, Procurement, Supply Chain, Inventory, Warehouse,
Logistics, Finance, Treasury, Risk, Medical, Mechanical, Electrical,
Automation, Developer, Architect, Cloud, Software Engineer, Data
Engineer) -- heavy by design, per "penalize heavily".

Debug logging (for troubleshooting why a specific job was accepted or
rejected, including its score) is emitted at DEBUG level -- enable it
with logging.basicConfig(level=logging.DEBUG); silent by default.

Patterns are plain lists (data), not scattered if/else branches --
extending the vocabulary later is a one-line edit to a list.
"""
import logging
import re

import app.env  # noqa: F401  (loads .env as an import side effect, before PROFILE is read below)

logger = logging.getLogger(__name__)

ACCEPTANCE_THRESHOLD = 60


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def _matches_any(patterns: list[re.Pattern], text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in patterns)


def _count_matches(patterns: list[re.Pattern], text: str) -> int:
    if not text:
        return 0
    return sum(1 for p in patterns if p.search(text))


# =============================================================================
# PPQM profile
# =============================================================================

# Hard veto -- an unrelated SAP module, or a generic supply-chain/
# procurement/logistics/sales/finance/engineering/IT role word.
# Suffix-agnostic (bare tokens) so "NPI Buyer", "Strategic Sourcing
# Manager", "SAP APO PPDS Consultant", etc. are all caught regardless
# of surrounding words. Checked BEFORE any accept-tier check, so e.g.
# "SAP APO PPDS" is rejected (APO present) while plain "SAP PPDS" (no
# APO) is unaffected -- no separate special-case logic needed for that
# distinction, it falls out naturally from checking reject first.
PPQM_REJECT_PATTERNS = _compile([
    r"\bbuyer\b", r"\bpurchasing\b", r"\bprocurement\b",
    r"\bsourcing\b", r"\bwarehouse\b", r"\binventory\b", r"\blogistics\b",
    r"\btransportation\b", r"\bplanner\b", r"\bsupply\s*chain\b",
    r"\bnpi\b", r"\bpresales\b", r"\bsolutions\s*engineer\b", r"\bsales\b",
    r"\baccount\s*executive\b", r"\baccount\s*manager\b", r"\bproject\s*manager\b",
    r"\bbusiness\s*development\b", r"\bbusiness\s*analyst\b", r"\boperations\b",
    r"\bfinance\b", r"\brisk\b", r"\btreasury\b", r"\bmedical\b",
    r"\bmechanical\b", r"\belectrical\b", r"\bautomation\b", r"\bdeveloper\b",
    r"\barchitect\b", r"\bdata\s*engineer\b", r"\bcloud\b", r"\bdevops\b",
    r"\bnetwork\b", r"\bsecurity\b", r"\binfrastructure\b", r"\bsoftware\s*engineer\b",
    r"\babap\b", r"\bbasis\b", r"\bfico\b", r"\bsuccessfactors\b", r"\bariba\b", r"\bbtp\b",
    r"\bsap\s*sd\b", r"\bsap\s*tm\b", r"\bewm\b", r"\bibp\b", r"\bapo\b",
])

# Band: 100 -- exact core title only (full-string anchored, minor
# whitespace/case variation allowed, but not extra words).
TITLE_EXACT_PATTERNS = _compile([
    r"^\s*sap\s+pp\s+consultant\s*$",
    r"^\s*sap\s+qm\s+consultant\s*$",
    r"^\s*sap\s+pp\s*/\s*qm\s+consultant\s*$",
])

# Band: 95-99 -- very strong, specific titles. Includes a
# suffix-agnostic bare PP/QM fallback (as in V11-V13) so titles like
# "SAP QM Analyst" or "SAP PP Support" still score well rather than
# falling through to reject-by-default -- the "exact" band above is
# checked first and reserved strictly for the 3 literal Consultant-
# suffix phrases, so this doesn't blur that distinction.
TITLE_VERY_STRONG_PATTERNS = _compile([
    r"\bsap\s*production\s*planning\s*consultant\b",
    r"\bsap\s*s\s*/\s*4\s*hana\s*pp\s*consultant\b",
    r"\bsap\s*s4\s*pp\s*consultant\b",
    r"\bsap\s*pp\s*lead\b",
    r"\bsap\s*ppds\s*consultant\b",
    r"\bpp[\s/-]+qm\b",     # SAP PP/QM, SAP PP QM, SAP PP-QM (any suffix)
    r"\bsap\s*pp\b",        # SAP PP + any suffix (Analyst, Support, Specialist, ...)
    r"\bsap\s*qm\b",        # SAP QM + any suffix
    r"\bpp\b",              # bare PP token -- combined titles like "SAP MM/PP Consultant"
    r"\bqm\b",              # bare QM token
    r"\bppds\b",            # PPDS / SAP PPDS on its own (rejected only when combined with APO, tier 0 above)
    r"\bsap\s*production\s*planning\b",
])

# Band: 60-84 -- weak, vague-but-SAP-adjacent titles.
TITLE_WEAK_PATTERNS = _compile([
    r"\bsap\s*manufacturing\s*consultant\b",
    r"\bsap\s*planning\s*consultant\b",  # deliberately NOT "production planning" -- that's very-strong above
])

# Narrow ambiguous role-word titles -> route to the "good" band's
# description check (both group A and group B required). Same list as
# V13, still only reached if title didn't already match reject/exact/
# very-strong/weak above.
PPQM_AMBIGUOUS_TITLE_PATTERNS = _compile([
    r"\bsenior\s+consultant\b",
    r"\blead\s+consultant\b",
    r"\bprincipal\s+consultant\b",
    r"\bfunctional\s+consultant\b",
    r"\bconsultant\b",
])

# Group A: PP/QM-domain evidence for the "good" band's description check.
PPQM_DESCRIPTION_GROUP_A_PATTERNS = _compile([
    r"\bsap\s*pp\b", r"\bpp\b", r"\bsap\s*qm\b", r"\bqm\b",
    r"\bproduction\s*planning\b", r"\bquality\s*management\b", r"\bpp\s*/\s*qm\b",
    r"\bppds\b", r"\brouting\b", r"\bmrp\b", r"\bproduction\s*orders?\b", r"\binspection\s*lot\b",
])

# Group B: implementation-flavored evidence for the "good" band's description check.
PPQM_DESCRIPTION_GROUP_B_PATTERNS = _compile([
    r"\bconfiguration\b", r"\bcustomizing\b", r"\bimplementation\b", r"\brollout\b",
    r"\bsupport\b", r"\benhancement\b", r"\bblueprint\b", r"\btesting\b",
    r"\bs\s*/\s*4\s*hana\b", r"\becc\b", r"\bfunctional\s*consultant\b",
])

# Description BONUS keywords -- implementation activities. +2 each,
# capped per-band (see _apply_bonus_penalty).
DESCRIPTION_BONUS_PATTERNS = _compile([
    r"\bconfiguration\b", r"\bcustomizing\b", r"\bimplementation\b", r"\brollout\b",
    r"\bsupport\b", r"\benhancement\b", r"\bblueprint\b", r"\btesting\b",
    r"\bmrp\b", r"\bproduction\s*orders?\b", r"\brouting\b", r"\binspection\s*lot\b",
    r"\bbatch\s*management\b", r"\bmaster\s*data\b", r"\bs\s*/\s*4\s*hana\b", r"\becc\b",
])
BONUS_PER_KEYWORD = 2

# Description PENALTY keywords -- generic/unrelated activities. -10
# each (heavy, by design -- "penalize heavily").
DESCRIPTION_PENALTY_PATTERNS = _compile([
    r"\bsales\b", r"\bpresales\b", r"\bprocurement\b", r"\bsupply\s*chain\b",
    r"\binventory\b", r"\bwarehouse\b", r"\blogistics\b", r"\bfinance\b",
    r"\btreasury\b", r"\brisk\b", r"\bmedical\b", r"\bmechanical\b",
    r"\belectrical\b", r"\bautomation\b", r"\bdeveloper\b", r"\barchitect\b",
    r"\bcloud\b", r"\bsoftware\s*engineer\b", r"\bdata\s*engineer\b",
])
PENALTY_PER_KEYWORD = 10


def _apply_bonus_penalty(base: int, band_ceiling: int, description: str) -> int:
    bonus = _count_matches(DESCRIPTION_BONUS_PATTERNS, description) * BONUS_PER_KEYWORD
    penalty = _count_matches(DESCRIPTION_PENALTY_PATTERNS, description) * PENALTY_PER_KEYWORD
    score = min(base + bonus, band_ceiling) - penalty
    return max(0, min(100, score))


def score_job(job: dict) -> int:
    """
    Computes a 0-100 relevance score for a job dict. Used only to make
    the keep/reject decision (see is_relevant) -- never persisted to
    the database, never returned by the API.
    """
    title = (job.get("title") or "").strip()
    description = job.get("description") or ""

    # Hard veto -- never rescued by description.
    if _matches_any(PPQM_REJECT_PATTERNS, title):
        return 0

    # Band: 100 (exact core title). Penalty can still reduce it (a
    # mismatched/low-quality description under a great title is a
    # legitimate quality signal); bonus is irrelevant, already at ceiling.
    if _matches_any(TITLE_EXACT_PATTERNS, title):
        return _apply_bonus_penalty(base=100, band_ceiling=100, description=description)

    # Band: 95-99 (very strong).
    if _matches_any(TITLE_VERY_STRONG_PATTERNS, title):
        return _apply_bonus_penalty(base=95, band_ceiling=99, description=description)

    # Band: 60-84 (weak, vague-but-SAP-adjacent).
    if _matches_any(TITLE_WEAK_PATTERNS, title):
        return _apply_bonus_penalty(base=65, band_ceiling=84, description=description)

    # Band: 85-94 (good) -- narrow ambiguous role-word title, requires
    # BOTH description evidence groups to even enter this band at all;
    # missing either -> 0 (matches V13's "reject if missing either group").
    if _matches_any(PPQM_AMBIGUOUS_TITLE_PATTERNS, title):
        has_group_a = _matches_any(PPQM_DESCRIPTION_GROUP_A_PATTERNS, description)
        has_group_b = _matches_any(PPQM_DESCRIPTION_GROUP_B_PATTERNS, description)
        if has_group_a and has_group_b:
            return _apply_bonus_penalty(base=85, band_ceiling=94, description=description)
        return 0

    # Reject by default -- title matched none of the bands above.
    return 0


def _is_relevant_ppqm(job: dict) -> bool:
    title = (job.get("title") or "").strip()
    score = score_job(job)
    accepted = score >= ACCEPTANCE_THRESHOLD

    if accepted:
        logger.debug("Accepted: %s (score=%d)", title, score)
        return True

    # Below threshold -- figure out which debug message is more useful.
    # A title in the ambiguous-role-word band that failed the
    # description check gets "Rejected by description"; everything
    # else (hard-veto reject, or a title matching no band at all) gets
    # "Rejected by title", since the description was never the deciding factor.
    if _matches_any(PPQM_AMBIGUOUS_TITLE_PATTERNS, title) and not (
        _matches_any(PPQM_REJECT_PATTERNS, title)
        or _matches_any(TITLE_EXACT_PATTERNS, title)
        or _matches_any(TITLE_VERY_STRONG_PATTERNS, title)
        or _matches_any(TITLE_WEAK_PATTERNS, title)
    ):
        logger.debug("Rejected by description: %s (score=%d)", title, score)
    else:
        logger.debug("Rejected by title: %s (score=%d)", title, score)

    return False


# =============================================================================
# Profile dispatch
# =============================================================================
# Single-profile app (Rajat, SAP PP/QM Manufacturing only) -- there is no
# HR ruleset and no PROFILE env var branching anymore. is_relevant()
# always applies the PPQM scoring rules above.


def is_relevant(job: dict) -> bool:
    """Applies the PPQM scoring ruleset (the only ruleset this app has)."""
    return _is_relevant_ppqm(job)


def filter_relevant(jobs: list[dict]) -> tuple[list[dict], int]:
    """Splits jobs into (kept, dropped_count). Same interface as before --
    collectors/runner.py calls this unchanged. Job dicts are returned
    exactly as given -- no score field is ever attached to them."""
    kept = [j for j in jobs if is_relevant(j)]
    dropped = len(jobs) - len(kept)
    return kept, dropped
