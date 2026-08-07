"""
Location normalization for the sidebar location filter and dashboard
statistics. Doesn't touch the database -- `location` stays exactly
what the collector stored; this is a pure query-time classification,
same spirit as the existing age-filtering in app/main.py.

Data-driven and extensible: each bucket is just a list of substrings
to match against the raw location (case-insensitive). Add a city to
grow a bucket's coverage; add a new dict entry to add a whole new
bucket -- no other code needs to change.
"""
import re

# Order matters: checked top to bottom, first match wins. "Other" is
# not listed here -- it's the fallback when nothing else matches.
LOCATION_BUCKETS = {
    "UAE": ["dubai", "abu dhabi", "sharjah", "uae", "united arab emirates", "ajman", "fujairah", "ras al khaimah"],
    "India": ["bangalore", "bengaluru", "mumbai", "delhi", "new delhi", "pune", "hyderabad",
              "chennai", "kolkata", "noida", "gurgaon", "gurugram", "india"],
    "Germany": ["berlin", "munich", "münchen", "frankfurt", "hamburg", "stuttgart", "cologne",
                "köln", "düsseldorf", "dusseldorf", "germany"],
    "UK": ["london", "manchester", "birmingham", "edinburgh", "glasgow", "united kingdom", "uk"],
    "Remote": ["remote"],
}

BUCKET_ORDER = ["All", "UAE", "India", "Germany", "UK", "Remote", "Other"]

_COMPILED_BUCKETS = {
    bucket: [re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE) for kw in keywords]
    for bucket, keywords in LOCATION_BUCKETS.items()
}


def normalize_location(raw: str) -> str:
    """Returns one of: UAE, India, Germany, UK, Remote, Other."""
    if not raw:
        return "Other"
    text = raw.strip()
    for bucket, patterns in _COMPILED_BUCKETS.items():
        if any(p.search(text) for p in patterns):
            return bucket
    return "Other"
