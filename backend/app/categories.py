"""
Job category classification, used for the sidebar's Job Category
filter. Independent from app/relevance.py's accept/reject scoring --
this only classifies already-stored jobs into labeled buckets for
filtering/faceting, it doesn't decide what gets saved.

Data-driven and extensible by design: a plain category, like "SAP PP"
or the future "MM"/"SD"/"FICO"/"ABAP"/"Buyer"/"Procurement", is just a
list of regex patterns checked against title+description. A composite
category, like "SAP PP/QM", is defined in terms of other categories
(here: requires both "SAP PP" and "SAP QM" to match) rather than its
own duplicated pattern list. Adding a new category is a one-line
addition to CATEGORY_DEFINITIONS -- no other code changes needed.
"""
import re


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


CATEGORY_DEFINITIONS = {
    "SAP PP": _compile([
        r"\bsap\s*pp\b", r"\bpp\b", r"\bppds\b", r"\bproduction\s*planning\b",
    ]),
    "SAP QM": _compile([
        r"\bsap\s*qm\b", r"\bqm\b", r"\bquality\s*management\b", r"\binspection\s*lot\b",
    ]),
    # --- Future categories go here the same way, e.g.:
    # "MM": _compile([r"\bsap\s*mm\b", r"\bmaterials\s*management\b"]),
    # "SD": _compile([r"\bsap\s*sd\b", r"\bsales\s*(and|&)\s*distribution\b"]),
    # "FICO": _compile([r"\bsap\s*fico\b", r"\bsap\s*fi\s*/?\s*co\b"]),
    # "ABAP": _compile([r"\babap\b"]),
    # "EWM": _compile([r"\bsap\s*ewm\b"]),
    # "PM" / "Project Manager": _compile([r"\bproject\s*manager\b"]),
    # "Buyer": _compile([r"\bbuyer\b"]),
    # "Procurement": _compile([r"\bprocurement\b"]),
    # "Supply Chain": _compile([r"\bsupply\s*chain\b"]),
}

# Composite categories: match only if the job matches ALL of the named
# plain categories above. Kept separate from CATEGORY_DEFINITIONS so
# _matches_plain_category() doesn't need special-case branching.
COMPOSITE_CATEGORY_DEFINITIONS = {
    "SAP PP/QM": ["SAP PP", "SAP QM"],
}

ALL_CATEGORIES = ["All Jobs"] + list(CATEGORY_DEFINITIONS.keys()) + list(COMPOSITE_CATEGORY_DEFINITIONS.keys())


def _matches_plain_category(job: dict, category: str) -> bool:
    patterns = CATEGORY_DEFINITIONS.get(category)
    if patterns is None:
        return False
    text = " ".join(filter(None, [job.get("title"), job.get("description")]))
    if not text:
        return False
    return any(p.search(text) for p in patterns)


def matches_category(job: dict, category: str) -> bool:
    """
    Returns True if `job` (a dict with at least "title"/"description")
    belongs to `category`. "All Jobs" (or falsy/unrecognized input)
    always matches everything.
    """
    if not category or category == "All Jobs":
        return True
    if category in COMPOSITE_CATEGORY_DEFINITIONS:
        return all(_matches_plain_category(job, c) for c in COMPOSITE_CATEGORY_DEFINITIONS[category])
    return _matches_plain_category(job, category)
