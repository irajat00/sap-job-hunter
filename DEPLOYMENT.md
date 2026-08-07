# Free deployment: GitHub Actions + GitHub Pages

This deploys the app with **no paid service and no credit card**, using
only GitHub's free tier:

- **Collector** (`backend/collectors/runner.py`, unmodified): runs on a
  schedule via **GitHub Actions** — every **15 minutes**.
- **Daily summary**: a second GitHub Actions workflow, once a day at 9 PM.
- **Frontend**: built and hosted on **GitHub Pages** (a free static
  file host).
- **Database** (`backend/jobs.db`, unmodified SQLite schema): persisted
  between runs using the **GitHub Actions cache**, and is **never
  committed to git** — only the generated `frontend/public/data/jobs.json`
  snapshot is committed. See "Why jobs.db is cached, not committed"
  below.
- **Telegram notifications**: unchanged — instant per-job notifications
  plus the once-daily summary, both with duplicate protection.

No backend server runs continuously anywhere. This is the key
architectural tradeoff of a 100%-free, GitHub-only deployment — see
"What does *not* work in this deployment" at the bottom before you
start.

---

## 1. Push this repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Use a **public** repo unless you're on a paid GitHub plan — GitHub
Actions minutes are unlimited/free on public repos; private repos get
a limited free monthly quota (usually enough for this app, but public
is simplest and guaranteed free).

`backend/jobs.db` is listed in `.gitignore`, so this commit will **not**
include it — that's intentional (see below).

---

## 2. Get your free API keys (if you don't already have them)

- **Adzuna**: free at https://developer.adzuna.com/ → gives you an App ID + App Key.
- **Jooble**: free at https://jooble.org/api/about → gives you an API key.
- **Telegram bot**: message **@BotFather** on Telegram → `/newbot` → copy
  the token it gives you. Then message your new bot anything (so it's
  allowed to message you back), then visit
  `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and read the
  `"chat":{"id": ...}` value — that's your chat ID.

---

## 3. Configure GitHub Secrets and Variables

In your repo on GitHub: **Settings → Secrets and variables → Actions**.

### Secrets tab — click "New repository secret" for each:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | your bot token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat ID |
| `ADZUNA_APP_ID` | your Adzuna App ID |
| `ADZUNA_APP_KEY` | your Adzuna App Key |
| `JOOBLE_API_KEY` | your Jooble API key |

These are the same values you already have in `backend/.env` locally —
just copy them in. They're encrypted at rest and never shown in logs.

### Variables tab — click "New repository variable" (optional, all have safe defaults if skipped):

| Variable name | Example value |
|---|---|
| `ADZUNA_COUNTRIES` | `gb,ae,de,in,ca,au` |
| `JOB_MAX_AGE_DAYS` | `90` |
| `SEARCH_KEYWORDS` | `SAP PP,SAP QM,SAP PP/QM,SAP Production Planning,SAP Manufacturing,SAP APO PPDS,SAP S/4HANA PP,SAP S/4HANA Manufacturing,SAP Digital Manufacturing` |
| `SEARCH_LOCATIONS` | (leave unset to use the built-in default list) |

(Variables ≠ Secrets: Variables are for non-sensitive config and are
visible in the UI; Secrets are for anything sensitive. Both are read
by the workflows the same way.)

---

## 4. Enable GitHub Pages

1. **Settings → Pages**.
2. Under "Build and deployment" → **Source**, select **"GitHub
   Actions"** (not "Deploy from a branch").
3. That's it — no further config needed here. The
   `deploy-pages.yml` workflow (already in this repo) handles the
   build and deployment.

---

## 5. Enable Actions and trigger the first runs

1. Go to the **Actions** tab. If prompted, click **"I understand my
   workflows, go ahead and enable them"**.
2. You should see 3 workflows: **Collect SAP jobs**, **Daily SAP job
   summary**, **Deploy frontend to GitHub Pages**.
3. Click **Collect SAP jobs** → **Run workflow** (top right) → **Run
   workflow** button in the dropdown. Wait for it to finish (green
   checkmark) — this does your first live collector run, generates
   `jobs.json`, and commits it.
4. That commit automatically triggers **Deploy frontend to GitHub
   Pages** — watch it run, then finish.
5. Your site is now live at:
   `https://<your-username>.github.io/<your-repo>/`
   (also shown under Settings → Pages once deployed).

From here on, both scheduled workflows run automatically:
**every 15 minutes** (collector) and **once daily at 9 PM** (summary,
UTC by default — see step 6).

---

## 6. Set your timezone for the 9 PM daily summary (optional)

By default, `.github/workflows/daily-summary.yml` sends the daily
summary at **21:00 UTC**. To make it your local 9 PM, edit that file's
`timezone:` line to your IANA timezone name, e.g.:

```yaml
on:
  schedule:
    - cron: '0 21 * * *'
      timezone: 'Asia/Kolkata'   # or 'Europe/Berlin', 'America/New_York', etc.
```

Commit and push the change — no other steps needed.

---

## 7. Keep the schedule alive (60-day rule)

GitHub automatically **disables scheduled workflows after 60 days with
no repository activity**. In practice this app's own automated commits
(from the collector pushing `jobs.json` updates whenever new jobs are
found) count as activity and reset that clock — but if your search
keywords are narrow and go a while with zero new jobs, no commit
happens. As a safety net, GitHub will email you if a schedule gets
disabled; if that happens, just go to the Actions tab → the workflow →
click **"Enable workflow"** again (one click).

---

## Why jobs.db is cached, not committed

GitHub Actions runners are ephemeral — nothing on disk survives
between runs unless the workflow saves it somewhere. There's no free,
always-on disk GitHub Actions can attach directly. Two options exist:
commit the database to git (simple, but bloats repo history with a
binary file on every run), or persist it with the **GitHub Actions
cache** (`actions/cache`) instead — still 100% free, still native to
GitHub, but never touches git history.

This project uses the cache: each run restores the most recently saved
`backend/jobs.db` (via a `restore-keys` prefix match — the standard
GitHub Actions pattern for "always get the latest version of some
evolving state"), runs the collector against it, and saves the updated
file back under a new cache key for the next run to find. Only the
generated `jobs.json` — never `jobs.db` itself — is ever committed.
Cache entries are capped at 10GB total per repo and old ones are
evicted automatically (least-recently-used first, and anything
untouched for 7+ days), so no manual cleanup is needed for a SQLite
file this size.

One tradeoff worth knowing: because the cache (not git) is now the
source of truth for accumulated job history, you won't see `jobs.db`
grow in your git history or on your local machine unless you
explicitly download it. `jobs.json` — which contains the full
accumulated job list — is committed and always current, so this
doesn't affect the live site at all.

---

## Installing the app on your phone (PWA)

The frontend is a Progressive Web App -- no App Store/Play Store
listing needed, and no backend or workflow changes were required to
add this (icons, `manifest.json`, and the service worker all live in
`frontend/public/`, copied into the build automatically, same as
`jobs.json`).

**Android (Chrome):** visit the site → a banner or the ⋮ menu offers
**"Install app" / "Add to Home screen"** → tap it. The app opens in its
own window with no browser address bar.

**iPhone/iPad (Safari):** open the site in Safari (not Chrome -- iOS
requires Safari for this) → tap the **Share** icon → **"Add to Home
Screen"**. iOS has no automatic install prompt (Apple has never
supported the `beforeinstallprompt` API Android uses) -- this manual
step is the only way to install a PWA on iOS, but the result looks and
behaves the same: full-screen, no browser chrome, app icon on the home
screen.

**Updates:** every new deployment gets a distinct cache automatically
(tied to the git commit that built it), so opening the app again after
a new deployment fetches the latest version and discards the old
cached one -- nothing to configure, nothing the user needs to do.

**Offline:** once loaded, the app shell and the last-fetched job list
work without a network connection; pull-to-refresh or the Settings tab's
"Refresh now" button will show an error until connectivity returns, but
won't break the rest of the app.

---



- [ ] **Collector runs every 15 minutes** — Actions tab → "Collect SAP
      jobs" shows runs roughly every 15 minutes (GitHub's scheduler is
      best-effort; occasional delays of a few minutes during peak load
      are a known, documented GitHub limitation, not a bug in this
      setup).
- [ ] **Telegram instant notifications work** — after the first manual
      run, check your Telegram chat for `🚨 New SAP Job Found!`
      messages, one per new job.
- [ ] **No duplicate notifications** — run "Collect SAP jobs" via
      "Run workflow" twice in a row; the second run's log will show
      the jobs as duplicates and send zero new notifications (the
      cache correctly restores the same `jobs.db` state between runs,
      so the same `telegram_notified` protection as your local setup
      applies unchanged).
- [ ] **Daily summary works** — Actions tab → "Daily SAP job summary"
      → "Run workflow" to test it immediately rather than waiting for
      9 PM; check Telegram for the `📊 Daily SAP Job Summary` message.
- [ ] **jobs.json is generated correctly and persists** — open
      `frontend/public/data/jobs.json` in the repo on GitHub after a
      few collector runs and confirm the job count is growing, not
      resetting to zero.
- [ ] **Frontend is live** — visit
      `https://<your-username>.github.io/<your-repo>/` and confirm
      jobs are listed, search/filter/sort/pagination/bookmarks/
      dashboard/categories/countries all work.
- [ ] **Installable as a PWA** — Chrome/Android shows an install
      option; on iPhone, Safari's Share → "Add to Home Screen" adds an
      icon that opens full-screen with no browser chrome.
- [ ] **Works offline after first load** — turn off Wi-Fi/data after
      opening the app once; the shell and last-loaded jobs still render.

---

## What does *not* work in this deployment

A 100%-free, GitHub-only setup has no continuously-running server, so
two frontend features that would need one were removed entirely
(not just disabled) since they're no longer relevant to a static-site
deployment:

- **Collector Status widget** — removed.
- **Export CSV / Excel / PDF buttons** — removed.

Everything else works fully, including the dashboard totals (Total
Jobs / New Today / Latest Jobs) — these are computed client-side from
the same static `data/jobs.json` snapshot as the rest of the app (see
`frontend/src/api.js`'s `fetchDashboard()`), not from a live endpoint.

If you ever want the Collector Status widget or file export back, the
only way is running the FastAPI backend somewhere continuously (which
necessarily means either a paid host, or a machine you keep on — both
explicitly out of scope for this deployment).
