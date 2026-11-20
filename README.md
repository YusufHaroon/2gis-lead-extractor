# 2GIS Business Lead Extractor

A responsive web app that searches for businesses by **category** and **location**, shows each
business's **name** and **at most one publicly displayed phone number**, and exports the results to
Excel when the data source's licence allows it.

- **Frontend:** Next.js 14, React 18, Tailwind CSS
- **Backend:** FastAPI, Playwright (Chromium), openpyxl
- **Collectors:** these are interchangeable. Out of the box there is a mock source and a local
  test page. A live 2GIS collector exists but is **disabled by default**.

> No n8n and no 2GIS API key are needed for the mock and local-test sources.

---

## Contents
- [Quick start (local)](#quick-start-local)
- [Using the dashboard](#using-the-dashboard)
- [Configuration](#configuration)
- [Data sources (collectors)](#data-sources-collectors)
- [API](#api)
- [Data rules](#data-rules)
- [Testing](#testing)
- [Docker](#docker)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Source permissions & compliance](#source-permissions--compliance)

---

## Quick start (local)

**Prerequisites:** Python 3.12 (3.10+ works) and Node.js 20+.

### 1. Backend (terminal 1)
```powershell
cd backend
py -3.12 -m venv .venv                 # macOS/Linux: python3.12 -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt    # runtime + test dependencies
playwright install chromium            # browser used by the local_fixture collector
copy .env.example .env                 # macOS/Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
The API docs are at http://localhost:8000/docs.

### 2. Frontend (terminal 2)
```powershell
cd frontend
copy .env.local.example .env.local     # macOS/Linux: cp .env.local.example .env.local
npm install
npm run dev
```
Then open **http://localhost:3000**.

---

## Using the dashboard

1. Enter a **category**. You can pick a suggestion such as *Restaurants*, *Clinics* or *Hotels*, or
   type your own.
2. Enter a **city or country**.
3. Optionally, set **Max results**. If you leave it blank, the server limit applies.
4. Choose a **data source**. Only enabled sources are listed.
5. Click **Start Collection**. While the search runs, the form is locked to prevent duplicate
   submissions, results appear as they are collected, and you can **Cancel**.
6. When the search finishes, click **Download Excel**. The button only works for completed
   searches from sources that allow export. If it is disabled, the dashboard shows the reason.

A search can end in one of these states:
- **Completed:** the source has no more results, or the max-results limit was reached.
- **Failed:** for example a timeout, or the source page layout changed. Results collected before
  the failure are kept and shown.
- **Cancelled:** results collected before cancelling are kept and shown.

---

## Configuration

### Backend: `backend/.env`
See [`backend/.env.example`](backend/.env.example). Every setting is optional.

| Variable | Default | Meaning |
|---|---|---|
| `DEFAULT_COLLECTOR` | `mock` | Source used when a request doesn't name one. |
| `ENABLE_LIVE_COLLECTOR` | `false` | Allows the live 2GIS source to run. It never enables export. |
| `MAX_RESULTS_CAP` | `200` | Maximum results per search. Requests above this are clamped. |
| `COLLECTOR_TIMEOUT_SECONDS` | `120` | Maximum run time for a search. |
| `MAX_CONCURRENT_JOBS` | `3` | Number of searches that can run at once. Extra requests get HTTP 429. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of dashboard URLs allowed to call the API. |

### Frontend: `frontend/.env.local`
| Variable | Default | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | The backend URL **as seen by the user's browser**. It is inlined at build time. |

---

## Data sources (collectors)

Collectors are in [`backend/app/collectors/`](backend/app/collectors). Each one implements
`BaseCollector.collect()`. Site-specific selectors and navigation logic stay inside the
collector's own module, so changing a source never touches the API, the processing code, the
export code or the dashboard.

| Source | What it does | Export |
|---|---|---|
| `mock` | 25 placeholder businesses (`Example …`, `+971 4 000 ….`). It includes blank phones, a business with several phones, and a duplicate. Simulates a delay so progress is visible. | Allowed |
| `local_fixture` | Uses Playwright and Chromium to read [`backend/fixtures/`](backend/fixtures): two linked pages covering pagination, a duplicate across pages, hidden phones and listings without IDs. | Allowed |
| `twogis` | Live 2GIS via the official **Catalog API** (no scraping, no browser, no CAPTCHA). Disabled until switched on and a key is set. | Allowed (export rights confirmed) |

### Enabling the live 2GIS source
1. Set these in `backend/.env`:
   ```ini
   ENABLE_LIVE_COLLECTOR=true
   TWOGIS_API_KEY=your-catalog-api-key
   ```
2. Restart the backend. The source then appears in the dashboard's picker as **2GIS (live API)**.

The key is read server-side only and is never sent to the browser. It **must be licensed for
contact data** (the `items.contact_groups` field); otherwise the API returns business names and
addresses but no phone numbers, so every phone cell comes back blank. A plain Demo/SDK key does
not include contact data. The source stays hidden until both the switch and a key are set.

### Adding a source
1. Create `app/collectors/<name>.py` with a subclass of `BaseCollector` that sets `name`,
   `label` and `export_allowed`.
2. In `collect()`, yield `RawListing` objects. `max_results` counts **distinct businesses**, not
   raw listings. Raise `CollectorError("…")` for failures that should be shown to the user.
3. For a browser-based source, wrap the work in `iterate_in_thread()` (see `local_fixture.py`) so
   it runs under any server event loop, including on Windows.
4. Register the class in `app/collectors/registry.py`.

---

## API

| Method & path | Purpose | Notable responses |
|---|---|---|
| `POST /api/jobs` | Start a search: `{category, location, max_results?, source?}` | `202`. `400` unknown source, `403` source disabled, `422` invalid input, `429` too many running |
| `GET /api/jobs/{id}` | Status, `collected`, `total_expected`, `export_allowed`, `error` | `404` unknown or expired job |
| `GET /api/jobs/{id}/results` | Cleaned records. Partial while the job is still running | `404` |
| `POST /api/jobs/{id}/cancel` | Cancel a running search | `409` already finished |
| `GET /api/jobs/{id}/export` | `.xlsx` download | `409` not completed, `403` export not permitted |
| `GET /api/sources` | Sources with `label`, `enabled`, `export_allowed`, `is_default` | |
| `GET /health` | Health check | |

Jobs are stored **in memory**. This is enough for the MVP, but jobs are lost when the server
restarts, and only the 100 most recent jobs are kept. For durable history, or for running many
searches at scale, add storage (for example SQLite) and a job queue.

---

## Data rules

These are implemented in [`app/services/processing.py`](backend/app/services/processing.py) and
[`app/services/exporter.py`](backend/app/services/exporter.py):

- **One phone at most:** the first publicly displayed number that contains a digit is kept.
  Hidden numbers are ignored. If there is no number, the cell is left **blank**.
- **Numbers are never changed:** only surrounding whitespace is trimmed. Numbers are not guessed,
  reformatted or invented.
- **Duplicates:** businesses are matched by the source's ID when there is one. Otherwise they are
  matched by name plus location, ignoring case, extra spaces and differences in Unicode encoding.
  The first occurrence is kept.
- **Excel:** the file has exactly two columns, `Business Name` and `Phone Number`, with one row per
  business. Every cell is stored as text, so phone numbers keep their `+`, and a name beginning
  with `=` is never run as a formula (formula-injection protection).

---

## Testing

### Backend unit and API tests (105 tests)
```powershell
cd backend
.venv\Scripts\python -m pytest                       # everything, about 15 s (launches Chromium)
.venv\Scripts\python -m pytest -m "not playwright"   # fast subset without a browser, about 1 s
```

### Browser end-to-end tests (14 tests)
These drive the real dashboard in Chromium. They reuse servers already running on `:3000` and
`:8000`, or start both servers themselves if those ports are free.
```powershell
backend\.venv\Scripts\python -m pytest e2e           # run from the repo root, about 60 s
```
They cover:
- the idle state, form validation, running, completed and cancelled states
- downloading the Excel file
- mobile, tablet and desktop layouts
- the local test-page source
- simulated empty, failed, "export not permitted", 429 and backend-unreachable states

### Frontend checks
```powershell
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

---

## Docker

```bash
docker compose up --build
```
This needs Docker Compose v2.24 or later, because it uses an optional `env_file`. It serves the dashboard at http://localhost:3000 and the API at http://localhost:8000.

- **Backend image:** `mcr.microsoft.com/playwright/python:v1.65.2-noble`, which includes Python 3.12
  and Chromium. It runs as a non-root user and has a health check. The tag **must match** the
  `playwright` version in `backend/requirements.txt`, so upgrade them together.
- **Frontend image:** a Next.js standalone build on `node:20-alpine`, run as a non-root user.
- **Settings:** if `backend/.env` exists, it is used. Compose-level overrides:
  ```bash
  NEXT_PUBLIC_API_URL=https://api.example.com CORS_ORIGINS=https://leads.example.com docker compose up --build
  ```
  `NEXT_PUBLIC_API_URL` is a **build argument**, because Next.js inlines it into the browser bundle.
  Changing it requires a rebuild (`--build`).

---

## Project structure
```
backend/
  app/
    main.py                 FastAPI app, CORS, shutdown hook
    config.py               settings from env / .env
    api/routes/             health, jobs, sources
    collectors/             base, registry, mock, local_fixture, twogis, threaded (browser thread helper)
    models/schemas.py       request/response models
    services/
      job_manager.py        in-memory jobs: run, limits, timeout, cancel, errors
      processing.py         phone selection, normalisation, deduplication
      exporter.py           .xlsx generation
  fixtures/                 local test listing pages
  tests/                    pytest suite
frontend/
  src/app/page.tsx          dashboard page
  src/components/           SearchPanel, JobStatus, ResultsTable, ExportButton
  src/lib/                  api client, useJob hook (polling), types, categories
e2e/                        browser end-to-end tests (pytest + Playwright)
docker-compose.yml
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard says "Can't reach the server" | Start the backend. Check that `NEXT_PUBLIC_API_URL` points to it and that `CORS_ORIGINS` includes the dashboard URL. The page retries on its own every 5 seconds. |
| `local_fixture` search fails immediately | Run `playwright install chromium` inside the backend venv. |
| `NotImplementedError` from Playwright on Windows | This is already handled: browser collectors run on their own event loop through `iterate_in_thread()`. Make sure any new browser collector uses it. |
| HTTP 429 when starting a search | `MAX_CONCURRENT_JOBS` searches are already running. Wait or cancel one, or raise the limit. |
| A search disappears after the backend restarts | Jobs are stored in memory (MVP). Start the search again. |
| Changed `NEXT_PUBLIC_API_URL` but nothing happened | It is fixed at build time. Restart `npm run dev`, or rebuild the Docker image. |

---

## Source permissions & compliance

- The live 2GIS collector is **off** (`ENABLE_LIVE_COLLECTOR=false`) and not implemented. Enable it
  only when the planned collection, storage and lead-generation export are authorized by the
  source's terms or by written permission. Even when it is enabled, Excel export for that source
  stays blocked unless `export_allowed` is changed deliberately after export rights are confirmed.
  If those rights can't be obtained, use an authorized provider with explicit lead-list export
  rights, added as a new collector.
- Collectors must **not** bypass CAPTCHAs, logins, anti-bot controls or other access
  restrictions, and must not use proxy rotation or stealth techniques.
- Results are limited to what the source actually shows. Complete coverage is not guaranteed.
- Use collected numbers in line with the source's licence and the applicable marketing, privacy
  and telemarketing rules. Automated calling or emailing, CRM syncing, enrichment and scheduling
  are out of scope.
