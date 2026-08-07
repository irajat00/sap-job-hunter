# SAP PP/QM Job Dispatch Board — Frontend

A Vite + React frontend for the existing FastAPI job-collector backend.

## Setup
```bash
cd frontend
npm install
cp .env.example .env
```

`.env` just needs the backend's URL (defaults to the local dev server):
```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Run
Make sure the backend is running first (see `backend/README.md`):
```bash
uvicorn app.main:app --reload
```

Then, in a separate terminal:
```bash
npm run dev
```
Visit http://localhost:5173

## Build for production
```bash
npm run build
```
Output lands in `dist/`. Serve it with any static file host; update
`VITE_API_BASE_URL` and the backend's CORS `allow_origins` (in
`app/main.py`) if you deploy the frontend somewhere other than
localhost.

## What it does
- Fetches jobs from the backend's existing `GET /jobs` endpoint
  (unchanged) at `limit=500` -- the backend's own max
- Search by keyword, filter by source, filter by location, and
  paginate -- all done client-side over that one fetched batch, since
  the backend has no free-text search endpoint and wasn't modified to
  add one. For a personal collector this ceiling (500 postings) is
  generous; if the database ever holds more than that, the oldest ones
  beyond the first 500 returned won't be searchable here until the
  collector prunes older rows or the backend's `/jobs` endpoint gains
  real server-side search/paging.
- Each job renders as a card ("routing ticket") showing title,
  company, location, salary (if present), a cleaned-up description
  snippet, and the source + posted date. Clicking a card opens the
  original `job_url` in a new tab.
- A "Refresh" button re-fetches from the backend (useful after the
  collector's scheduled runs add new postings).
- Loading, empty, and error states are all handled -- including a clear
  message if the backend isn't reachable.

## One small backend change
CORS support (`CORSMiddleware`) was added to `backend/app/main.py` so
this frontend (running on a different port) is allowed to call the
API at all -- browsers block cross-origin requests by default,
regardless of what the frontend code does. No routes, models, or
response shapes were changed. See the note in `backend/README.md`.
