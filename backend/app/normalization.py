"""
Data-quality helpers: normalization for company/title/location/salary
comparison (used to strengthen duplicate detection and search without
touching score_job(), schema, or the existing job_url-based dedup
itself), plus a labeled salary estimate for jobs missing one.

Never overwrites the original `salary` column -- estimates are
returned as a separate ephemeral field, same pattern as relevance_score.
"""
import re

_SUFFIX_RE = re.compile(r"\b(gmbh|inc\.?|llc|ltd\.?|corp\.?|co\.?|pvt\.?|limited|group)\b", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def normalize_company(name: str) -> str:
    if not name:
        return ""
    cleaned = _SUFFIX_RE.sub("", name)
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return _WS_RE.sub(" ", cleaned).strip().lower()


def normalize_title(title: str) -> str:
    if not title:
        return ""
    cleaned = re.sub(r"[^\w\s/]", " ", title)
    return _WS_RE.sub(" ", cleaned).strip().lower()


def normalize_location_text(location: str) -> str:
    if not location:
        return ""
    return _WS_RE.sub(" ", location).strip().lower()


def normalize_salary(salary: str):
    """Extracts (low, high) numeric bounds from a free-text salary
    string, or None if nothing parseable. Used only for comparison/
    estimation, never written back."""
    if not salary:
        return None
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]{3,}", salary)]
    if not nums:
        return None
    return (min(nums), max(nums))


# Very rough country/experience-tier baseline salary bands (annual,
# local currency-agnostic order-of-magnitude placeholders) -- clearly
# labeled as an estimate wherever surfaced, never presented as real data.
_BASE_BANDS = {
    "germany": (55000, 95000),
    "uae": (150000, 300000),
    "india": (1200000, 2800000),
    "uk": (45000, 80000),
    "remote": (50000, 100000),
}
_SENIOR_MULTIPLIER = {"junior": 0.8, "mid": 1.0, "senior": 1.3, "lead": 1.5}


def estimate_salary(country_bucket: str, title: str) -> dict:
    band = _BASE_BANDS.get((country_bucket or "").lower())
    if not band:
        return {"estimated": False}
    title_lower = (title or "").lower()
    tier = "mid"
    for key in ["senior", "lead", "junior"]:
        if key in title_lower:
            tier = key
            break
    mult = _SENIOR_MULTIPLIER.get(tier, 1.0)
    low, high = int(band[0] * mult), int(band[1] * mult)
    return {"estimated": True, "low": low, "high": high, "basis": f"{country_bucket} / {tier} tier (rough estimate)"}
