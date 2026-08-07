# Job Collector — Backend

## Structure
```
backend/
├── app/
│   ├── main.py         FastAPI app, GET /jobs
│   ├── database.py     SQLAlchemy engine/session
│   ├── migrate.py      creates tables
│   ├── config.py       search keyword/location matrix
│   ├── relevance.py    filters out irrelevant SAP-module postings
│   └── models/
│       └── job.py      Job model
├── collectors/
│   ├── base.py          BaseCollector -- the interface every source implements
│   ├── adzuna.py         active -- free, licensed aggregator API
│   ├── jooble.py         active -- free, official aggregator API (see Jooble section)
│   ├── greenhouse.py      built + tested, NOT active -- per-company, needs curation
│   ├── lever.py           built + tested, NOT active -- per-company, needs curation
│   ├── ashby.py           built + tested, NOT active -- per-company, needs curation
│   ├── smartrecruiters.py built + tested, NOT active -- per-company, needs curation
│   ├── linkedin.py       stub -- needs official partner API
│   ├── naukri.py         stub -- needs official partner API
│   ├── foundit.py        stub -- needs official partner API
│   ├── jsearch.py        stub -- needs RapidAPI key
│   └── runner.py         sweeps the search matrix, dedupes, saves, notifies
├── notifiers/
│   └── telegram.py       free Telegram bot notifications
├── scripts/
│   ├── compare_sources.py        real Adzuna-vs-Jooble yield comparison (run it yourself)
│   ├── run_collector.bat         entry point for Task Scheduler
│   └── setup_task_scheduler.bat  registers the 15-min scheduled task
├── logs/                 collector run logs land here
├── requirements.txt
└── .env.example
```

## The collector architecture

Every source is a class implementing `BaseCollector`:

```python
class BaseCollector(ABC):
    source_name: str

    @abstractmethod
    def fetch_jobs(self, query: str, location: str = "") -> list[dict]:
        ...
```

`fetch_jobs` returns a list of dicts shaped like the `Job` model's fields
(`title`, `company`, `location`, `salary`, `source`, `job_url`,
`posted_date`, `description`). `job_url` is required -- it's the dedup key.

**To add a new source** (LinkedIn, Naukri, Foundit, JSearch, an official
employer API, whatever):
1. Create `collectors/<name>.py` with a class that subclasses `BaseCollector`
2. Set `source_name` and implement `fetch_jobs()`
3. Register an instance in `runner.py`'s `COLLECTORS` list

Nothing else -- the model, the search matrix, dedup logic, notifications,
the API -- needs to change.

## Naming note
`adzuna.py` is Adzuna's own API (developer.adzuna.com, free tier), not
Indeed. It's a licensed aggregator that includes some Indeed-sourced
listings among others, labeled honestly as its own source
(`source="adzuna"`).

Indeed, LinkedIn, and Naukri all prohibit automated scraping in their
terms of service and actively block bot traffic. `linkedin.py`,
`naukri.py`, and `foundit.py` are left as stubs pending their official
partner/employer APIs, so nothing here scrapes them directly.

## Search matrix
`app/config.py` defines the keywords and locations every run sweeps:

```python
KEYWORDS = ["SAP PP", "SAP PPDS", "SAP APO PPDS", "SAP Production Planning",
            "SAP QM", "SAP Quality Management", "SAP PP/QM",
            "SAP S/4HANA PP", "SAP S/4HANA Manufacturing", "SAP Manufacturing",
            "SAP Supply Chain Planning", "SAP IBP Supply Chain"]
LOCATIONS = ["Dubai", "Abu Dhabi", "UAE", "India", "Germany", "Remote"]
```

Every registered collector is queried once per (keyword, location) pair
-- 72 calls per collector per full run with the defaults above. There's
a 1-second delay between calls (`REQUEST_DELAY_SECONDS` in
`runner.py`) to stay well inside Adzuna's free-tier rate limit. Edit
the lists directly, or override per-run without editing the file:
```bash
SEARCH_KEYWORDS="SAP PP,SAP QM" SEARCH_LOCATIONS="Dubai" python -m collectors.runner
```

**Note on "Dubai" / "Abu Dhabi" / "UAE":** Adzuna has no Middle East /
Gulf coverage at all (see country note below), so these three location
filters currently return nothing from Adzuna, and Jooble's Gulf
coverage is unconfirmed (see Jooble section below). They're left in
the list so they activate automatically the moment a legitimate, free,
ToS-compliant Gulf-covering source is identified and added as a
collector -- none has been found yet (see "Sources considered and
rejected" below).

## Countries searched
Adzuna's API is per-country. `adzuna.py` queries every country in
`ADZUNA_COUNTRIES` (comma-separated) and merges + dedupes the results.
Adzuna genuinely supports 19 markets:

```
gb us de fr in ca au nz za pl nl it es at be br mx sg ch
```

**Correction from an earlier version of this project:** `ae` (UAE) was
previously included in the default list, but Adzuna does not actually
cover the UAE or any Gulf country -- that value was silently failing
every run. `.env.example` now lists the real 19 supported codes. A
country code that Adzuna rejects is still logged and skipped rather
than crashing the run, so a mistake there costs you a failed call, not
a broken pipeline.

**Call volume:** 72 (keyword x location) combos x 19 countries = up to
**1,368 Adzuna calls per full run**. That's almost certainly more than
Adzuna's free tier allows in one run, let alone every 15 minutes.
Before turning on the Task Scheduler job, either:
- trim `ADZUNA_COUNTRIES` to the markets you actually care about (e.g.
  just `de,in` if Germany and India are your real targets), and/or
- trim `KEYWORDS`/`LOCATIONS` via the `SEARCH_KEYWORDS`/`SEARCH_LOCATIONS`
  env overrides, and/or
- run less often than every 15 minutes (edit the schedule in
  `setup_task_scheduler.bat`).
Check your actual daily quota on your Adzuna developer dashboard --
free-tier limits aren't published as a fixed public number and can
vary by account.

## Relevance filtering
`app/relevance.py` runs on every batch of fetched jobs, before dedup
and saving. It drops postings that clearly target a different SAP
module (ABAP, Basis, FICO, MM, SD) *unless* the same posting also
mentions PP/QM-relevant terms (PP, QM, PPDS, Production Planning,
Quality Management, S/4HANA PP, Supply Chain Planning, etc.) --  so a
combined "SAP MM/PP" role is correctly kept, while a plain "SAP ABAP
Developer" posting that only got pulled in by a broad keyword match
gets dropped. Postings with no SAP-module signal either way (generic
"Production Planning Manager" roles, for instance) are kept by default.
The runner logs how many postings were filtered out per run
(`filtered_out` in the summary).

## Jooble — second free aggregator (active)
`jooble.py` adds Jooble (jooble.org/api/about) as a second
keyword+location-searchable aggregator alongside Adzuna. Like Adzuna:
free registration, no per-call cost, unauthenticated beyond your key.

Setup: get a free key at https://jooble.org/api/about, set
`JOOBLE_API_KEY` in `.env`.

It paginates automatically (up to `MAX_PAGES = 3` per keyword/location
combo, a safety cap against runaway call volume -- adjust the constant
in `jooble.py` if you want more or fewer pages per query) and stops
early once it's fetched everything Jooble reports via `totalCount`.

**Honest limitation on country coverage:** Jooble's own materials
confirm coverage of Germany, India, and most of Europe/North
America among "69 countries," but don't give a definitive list, so I
can't confirm whether the UAE is included. The collector doesn't
assume either way -- an uncovered region just returns zero results,
same as any other collector failure mode already handled by the runner.

**How many additional jobs does Jooble contribute vs. Adzuna?**
I can't tell you a real number -- this project's development sandbox
has no network access to `jooble.org` or `api.adzuna.com`, so I
couldn't run either API live to measure it. Rather than guess, use
`scripts/compare_sources.py` once you have both API keys:
```bash
python -m scripts.compare_sources
# or a single combo instead of the full matrix:
python -m scripts.compare_sources --query "SAP PP" --location "Germany"
```
It reports, per keyword/location and in total, how many jobs each
source returns and -- the number that actually matters -- how many of
Jooble's results are *net-new* (not already found by Adzuna, deduped by
`job_url`), since raw volume alone double-counts postings both sources
already agree on.

## Sources considered and rejected
Researched before building anything, so this project doesn't end up
scraping something it shouldn't or quietly relying on an unauthorized
endpoint:

- **Bayt.com**: No free official API exists -- only paid third-party
  scrapers (~$4-5/1,000 results). Not integrated; no placeholder file
  is kept for it.
- **Google Jobs**: No official public API for reading the aggregated
  index. Every "Google Jobs API" product found is a paid third-party
  service that scrapes Google Search result pages. Google Cloud Talent
  Solution is a different, paid, enterprise product for uploading your
  *own* postings into Google's search infra -- not a way to read
  others' listings. Not integrated.
- **Germany: Bundesagentur für Arbeit ("Arbeitsagentur")**: Confirmed
  from their own community-documented API repo that no official API
  exists -- what's out there is a reverse-engineered endpoint used
  internally by their own mobile app, not authorized for third-party
  use. Held to the same bar as Bayt/LinkedIn/Naukri; not integrated.
- **Workday**: The `wday/cxs/...` JSON endpoint each Workday-hosted
  career page uses internally is not an officially published
  third-party API. Not integrated.
- **India: National Career Service (NCS)**: No documented live,
  queryable third-party API found (only static/bulk datasets on
  data.gov.in of unclear scope); content also skews toward
  government/vocational listings rather than enterprise SAP roles. Not
  integrated.
- **RSS feeds** (WeWorkRemotely, RemoteOK, Himalayas): Legitimately
  free, but essentially zero SAP PP/QM relevance (pure startup/tech
  remote-job feeds). Considered and rejected on relevance grounds, not
  legality.

## ATS collectors (Greenhouse, Lever, Ashby, SmartRecruiters) — built, not active
`collectors/greenhouse.py`, `lever.py`, `ashby.py`, and
`smartrecruiters.py` each wrap an officially documented, free, public,
unauthenticated job-board API:
- Greenhouse: `boards-api.greenhouse.io/v1/boards/{company}/jobs`
- Lever: `api.lever.co/v0/postings/{company}`
- Ashby: `api.ashbyhq.com/posting-api/job-board/{company}`
- SmartRecruiters: `api.smartrecruiters.com/v1/companies/{company}/postings`

**The catch: none of these support keyword search across companies --
you query one company's full job list at a time by its slug** (the
part of its public job-board URL after `boards.greenhouse.io/`,
`jobs.lever.co/`, etc.). Each collector fetches its configured
companies' full lists (cached in memory for the life of one run, so
`runner.py`'s per-combo loop doesn't refetch the same data 72 times)
and filters locally by keyword/location.

They're deliberately **not registered in `runner.py`'s `COLLECTORS`
list right now** -- the company-owning ATS platforms skew toward
tech/startup employers, not the SAP-consulting/manufacturing firms
that post PP/QM roles, so their real yield for this specific niche is
uncertain and entirely dependent on curating a real list of relevant
companies. Rather than fabricate a list of companies I haven't
verified, they ship fully tested with an **empty company list by
default** (zero requests, zero jobs -- completely inert until
configured).

To find real company slugs: visit a company's careers page; if it
redirects to (or embeds) `boards.greenhouse.io/<slug>`,
`jobs.lever.co/<slug>`, `jobs.ashbyhq.com/<slug>`, or
`careers.smartrecruiters.com/<slug>`, that slug is what goes in
`GREENHOUSE_COMPANIES` / `LEVER_COMPANIES` / `ASHBY_COMPANIES` /
`SMARTRECRUITERS_COMPANIES` (comma-separated, in `.env` or
`app/config.py`). To activate once you've built a list worth trying,
uncomment the relevant import and add an instance to `COLLECTORS` in
`collectors/runner.py` -- one line each, no other changes needed.


```bash
cd backend
python -m venv venv
venv\Scripts\activate          (Windows)   or   source venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
copy .env.example .env         (Windows)   or   cp .env.example .env      (Mac/Linux)
```

1. Adzuna: free app_id/app_key at https://developer.adzuna.com/ -> put in `.env`
2. Jooble: free key at https://jooble.org/api/about -> put in `.env`
3. Telegram: see the setup steps in `notifiers/telegram.py` -> put token + chat_id in `.env`

All three are free. `.env` is loaded automatically (via `python-dotenv`, see
`app/env.py`) by every entry point -- `app.main`, `app.migrate`, and
`collectors.runner` -- so you don't need to export the variables
yourself or run anything with `source .env` first.

## Create the database
```bash
python -m app.migrate
```

## Collect jobs (manual run)
```bash
python -m collectors.runner
```
This sweeps the full keyword x location matrix and sends a Telegram
message listing any newly-found jobs. Use `--query`/`--location` to run
a single search instead of the full matrix (handy for testing), or
`--no-notify` to skip Telegram.

## Run the API
```bash
uvicorn app.main:app --reload
```
Then visit http://127.0.0.1:8000/jobs (or /docs for interactive API docs).
Filter with `?source=adzuna`, `?location=Dubai`, etc.

CORS is enabled for `http://localhost:5173` / `http://127.0.0.1:5173`
(the Vite dev server's default) so the React frontend can call this API
directly. If you serve the frontend from somewhere else, add that
origin to `allow_origins` in `app/main.py`.

## Automate with Windows Task Scheduler (free, built into Windows)
1. Fill in `.env` and confirm `python -m collectors.runner` works manually first.
2. Right-click `scripts\setup_task_scheduler.bat` -> **Run as administrator**.
   This registers a task named `SAP_PP_QM_Job_Collector` that runs
   `scripts\run_collector.bat` every 15 minutes.
3. Logs land in `logs\collector.log`.
4. To check on it: open Task Scheduler and find the task, or run
   `schtasks /Query /TN "SAP_PP_QM_Job_Collector"`.
5. To remove it: `schtasks /Delete /TN "SAP_PP_QM_Job_Collector" /F`

If `run_collector.bat`'s venv path doesn't match your setup, open it and
adjust `VENV_PATH` / `PROJECT_DIR` at the top.

## Everything above is free
Adzuna free tier, Jooble free tier, Telegram Bot API, SQLite, and
Windows Task Scheduler all have no cost. The only thing to watch is
each aggregator's free-tier daily call limit if you shorten the
15-minute interval or add more keywords/locations -- Jooble adds up to
`MAX_PAGES` (default 3) requests per keyword/location combo on top of
Adzuna's existing volume.
