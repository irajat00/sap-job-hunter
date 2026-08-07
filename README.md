# SAP PP/QM Job Collector

Collects SAP PP/QM Manufacturing job postings, sends instant Telegram
notifications for new matches, and browses results on a small web
frontend.

- `backend/` — FastAPI app, collector, Telegram notifier. See
  `backend/README.md` for local development.
- `frontend/` — React/Vite job-browsing UI. See `frontend/README.md`
  for local development.
- **`DEPLOYMENT.md`** — deploy this app for free using GitHub Actions
  + GitHub Pages (no paid service, no credit card). Start here if
  you want the collector running automatically in the cloud with your
  laptop off.
