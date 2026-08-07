"""
Search matrix — every (keyword, location) pair gets queried against each
registered collector.

KEYWORDS below is a fallback default. The authoritative source is the
SEARCH_KEYWORDS environment variable (comma-separated) -- set it in
.env and the app uses that instead, with no Python code changes ever
needed to change what's searched. Example:
    SEARCH_KEYWORDS=SAP PP,SAP QM,SAP PP/QM,SAP Production Planning,SAP Manufacturing,SAP APO PPDS,SAP S/4HANA PP,SAP S/4HANA Manufacturing,SAP Digital Manufacturing

Single fixed-user app: this app collects SAP Manufacturing (PP/QM)
jobs only -- no HR keyword set, no profile-based keyword switching.
KEYWORDS is simply "the" keyword list.
"""
import app.env  # noqa: F401  (loads .env as an import side effect)
import os

# Default SAP Manufacturing keyword set -- covers every keyword
# required by the current spec. SEARCH_KEYWORDS in .env overrides this
# entirely (see module docstring); this list is only the safety net for
# an empty/misconfigured .env.
KEYWORDS = [
    "SAP PP",
    "SAP QM",
    "SAP PP/QM",
    "SAP Production Planning",
    "SAP Manufacturing",
    "SAP APO PPDS",
    "SAP S/4HANA PP",
    "SAP S/4HANA Manufacturing",
    "SAP Digital Manufacturing",
]

# Note: no free, legally-usable automated source for UAE/Gulf job
# listings has been identified yet (Adzuna doesn't cover the region;
# Bayt.com has no free API and isn't scraped -- see collectors/README
# discussion). "Dubai", "Abu Dhabi", and "UAE" are kept here so they
# take effect automatically the moment a legitimate Gulf-covering
# source is added as a collector.
LOCATIONS = [
    "Dubai",
    "Abu Dhabi",
    "UAE",
    "India",
    "Germany",
    "Remote",
]

# Override either list via env vars if you want a smaller run without
# editing this file, e.g. for quick testing:
#   SEARCH_KEYWORDS="SAP PP,SAP QM" SEARCH_LOCATIONS="Dubai" python -m collectors.runner
if os.getenv("SEARCH_KEYWORDS"):
    KEYWORDS = [k.strip() for k in os.getenv("SEARCH_KEYWORDS").split(",") if k.strip()]
if os.getenv("SEARCH_LOCATIONS"):
    LOCATIONS = [l.strip() for l in os.getenv("SEARCH_LOCATIONS").split(",") if l.strip()]


# ---------------------------------------------------------------------
# ATS company lists (Greenhouse, Lever, Ashby, SmartRecruiters)
# ---------------------------------------------------------------------
# Each of these APIs is per-company, not keyword-searchable across all
# companies -- you supply the exact company "slug" from that company's
# public job board URL, e.g.:
#   boards.greenhouse.io/<slug>        -> GREENHOUSE_COMPANIES
#   jobs.lever.co/<slug>               -> LEVER_COMPANIES
#   jobs.ashbyhq.com/<slug>            -> ASHBY_COMPANIES
#   careers.smartrecruiters.com/<slug> -> SMARTRECRUITERS_COMPANIES
#
# Empty by default -- with no companies configured, each of these
# collectors makes zero requests and returns zero jobs (a safe no-op).
# Populate them once you've identified real companies in your target
# industries that use these platforms; see backend/README.md for how
# to find valid slugs. Comma-separated env overrides work the same way
# as SEARCH_KEYWORDS/SEARCH_LOCATIONS above.
GREENHOUSE_COMPANIES = []
LEVER_COMPANIES = []
ASHBY_COMPANIES = []
SMARTRECRUITERS_COMPANIES = []

if os.getenv("GREENHOUSE_COMPANIES"):
    GREENHOUSE_COMPANIES = [c.strip() for c in os.getenv("GREENHOUSE_COMPANIES").split(",") if c.strip()]
if os.getenv("LEVER_COMPANIES"):
    LEVER_COMPANIES = [c.strip() for c in os.getenv("LEVER_COMPANIES").split(",") if c.strip()]
if os.getenv("ASHBY_COMPANIES"):
    ASHBY_COMPANIES = [c.strip() for c in os.getenv("ASHBY_COMPANIES").split(",") if c.strip()]
if os.getenv("SMARTRECRUITERS_COMPANIES"):
    SMARTRECRUITERS_COMPANIES = [c.strip() for c in os.getenv("SMARTRECRUITERS_COMPANIES").split(",") if c.strip()]
