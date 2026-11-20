# 2GIS Business Lead Extractor

A responsive web app that searches for businesses by **category** and **location**, shows each
business's details, and exports the results to an Excel (`.xlsx`) file.

For every business it collects:

| Column | Notes |
|---|---|
| **Business Name** | Always available. |
| **Phone Number** | One publicly listed number, or blank. Requires a contact-data-licensed 2GIS key (see below). |
| **Address** | Street address. |
| **Category** | The business category from the source. |
| **Opening Hours** | Weekly hours in readable form, e.g. `Mon-Fri 09:00-22:00; Sat 10:00-18:00`. |

**Tech stack:** Next.js + React + Tailwind (frontend) · FastAPI + Playwright + openpyxl (backend).

---

## Table of contents

- [How it works](#how-it-works)
- [Before you start (prerequisites)](#before-you-start-prerequisites)
- [Step-by-step setup](#step-by-step-setup)
  - [1. Get the code](#1-get-the-code)
  - [2. Start the backend](#2-start-the-backend-api)
  - [3. Start the frontend](#3-start-the-frontend-dashboard)
  - [4. Open the app](#4-open-the-app)
- [Using the dashboard](#using-the-dashboard)
- [Data sources](#data-sources)
- [Getting a 2GIS API key (for live data)](#getting-a-2gis-api-key-for-live-data)
- [Configuration reference](#configuration-reference)
- [Running with Docker](#running-with-docker-optional)
- [Running the tests](#running-the-tests)
- [Troubleshooting](#troubleshooting)
- [Project structure](#project-structure)
- [Legal & responsible use](#legal--responsible-use)

---

## How it works

The app has two parts that run side by side:

- A **backend** (FastAPI, on port `8000`) that runs the searches and builds the Excel file.
- A **frontend** (Next.js, on port `3000`) that you use in your browser.

You can run the whole thing **without any API key** using the built-in demo sources. An API key is
only needed if you want to pull **live data from 2GIS** — see
[Getting a 2GIS API key](#getting-a-2gis-api-key-for-live-data).

---

## Before you start (prerequisites)

Install these first:

| Tool | Version | Check with | Where to get it |
|---|---|---|---|
| **Python** | 3.10–3.12 (3.12 recommended) | `python --version` | <https://www.python.org/downloads/> |
| **Node.js** | 20 or newer | `node --version` | <https://nodejs.org/> |
| **Git** | any recent | `git --version` | <https://git-scm.com/> |

> **Note on Python 3.13+:** some dependencies may not have ready-made installers for the very
> newest Python yet. If `pip install` fails, use Python 3.12. On Windows you can pick a version
> with the launcher, e.g. `py -3.12 -m venv .venv`.

You'll need **two terminal windows** — one for the backend, one for the frontend.

---

## Step-by-step setup

### 1. Get the code

```bash
git clone <your-repository-url> 2gis-lead-extractor
cd 2gis-lead-extractor
```

### 2. Start the backend (API)

In your **first terminal**:

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell/CMD):
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies (runtime + test tools)
pip install -r requirements-dev.txt

# Install the Chromium browser used by one of the demo sources
playwright install chromium

# Create your settings file from the example
# Windows:
copy .env.example .env
# macOS / Linux:
cp .env.example .env

# Run the server
uvicorn app.main:app --reload --port 8000
```

When it's running you'll see output ending in `Application startup complete`. Leave this terminal
open. You can confirm it works by visiting <http://localhost:8000/docs> (the interactive API docs).

### 3. Start the frontend (dashboard)

In your **second terminal**:

```bash
cd frontend

# Create the frontend settings file from the example
# Windows:
copy .env.local.example .env.local
# macOS / Linux:
cp .env.local.example .env.local

# Install dependencies
npm install

# Run the dashboard
npm run dev
```

Leave this terminal open too.

### 4. Open the app

Go to **<http://localhost:3000>** in your browser. You're ready to search.

> The default source is **Mock data**, which returns realistic placeholder businesses. This lets
> you try the whole app — searching, results, Excel export — without any API key.

---

## Using the dashboard

1. **Category** — pick a suggestion (Restaurants, Clinics, Hotels, …) or type your own.
2. **City or country** — e.g. `Dubai`.
3. **Max results** *(optional)* — leave blank to use the server limit.
4. **Data source** — pick which source to search (see below). Only enabled sources appear.
5. Click **Start Collection**. While it runs you'll see live progress, and you can **Cancel**.
6. When it finishes, click **Download Excel** to save the `.xlsx` file.

A search ends in one of these states:

- **Completed** — finished normally.
- **Cancelled** — you stopped it. Results collected so far are kept.
- **Failed** — e.g. a timeout or a source error. Any results collected before the failure are kept,
  and a clear message explains what happened.

---

## Data sources

| Source | What it is | Needs a key? | Export allowed? |
|---|---|---|---|
| **Mock data** | Realistic placeholder businesses. Great for trying the app. | No | Yes |
| **Local test page** | Reads a small sample web page using a real headless browser (Playwright). Demonstrates the browser-based collector. | No | Yes |
| **2GIS (live API)** | Real businesses from the official 2GIS Catalog API. | **Yes** | Yes |

The **2GIS** source only appears in the dashboard when it is switched on **and** an API key is
configured (see the next section).

---

## Getting a 2GIS API key (for live data)

You only need this if you want **real 2GIS results**. The demo sources need nothing.

### Step 1 — Request a key from 2GIS

2GIS API keys are issued by 2GIS, not by this project. Start from the official API documentation:

- **2GIS API docs:** <https://docs.2gis.com/en/api/search/places/overview>

You need a key for the **Places / Catalog API**. When requesting it, ask specifically for access to
**contact data (phone numbers)** — this is often a separate permission level (see the important note
below).

### Step 2 — Add the key to the backend

Open `backend/.env` and set:

```ini
ENABLE_LIVE_COLLECTOR=true
TWOGIS_API_KEY=your-key-here
```

Optionally, you can pin a region to skip the automatic region lookup:

```ini
# Example only — leave blank to resolve the region from the location you type.
TWOGIS_REGION_ID=
```

### Step 3 — Restart the backend

Stop the backend (`Ctrl+C` in its terminal) and start it again:

```bash
uvicorn app.main:app --reload --port 8000
```

**2GIS (live API)** will now appear as a data source in the dashboard.

> **⚠️ Important — phone numbers and your key type**
>
> The 2GIS Catalog API only returns phone numbers if your key is **licensed for contact data**.
> A basic **Demo / SDK** key will return business **names, addresses, categories and opening hours**,
> but the **Phone Number column will be blank** for every result. This is a limitation of the key,
> not of this app. To get phone numbers, obtain a Catalog API key that includes contact details.

> **🔒 Security:** the API key is read on the server only and is **never** sent to the browser.
> `backend/.env` is git-ignored, so your key won't be committed. Never paste a real key into the
> frontend or into any public place.

---

## Configuration reference

### Backend — `backend/.env`

All values are optional and have sensible defaults (see `backend/.env.example`).

| Setting | Default | What it does |
|---|---|---|
| `DEFAULT_COLLECTOR` | `mock` | Source used when a request doesn't name one. |
| `ENABLE_LIVE_COLLECTOR` | `false` | Turns the live 2GIS source on (also needs a key). |
| `TWOGIS_API_KEY` | *(empty)* | Your 2GIS Catalog API key. Server-side only. |
| `TWOGIS_REGION_ID` | *(empty)* | Optional fixed 2GIS region id; otherwise resolved from the location. |
| `TWOGIS_API_BASE` | `https://catalog.api.2gis.com` | 2GIS API host. |
| `MAX_RESULTS_CAP` | `200` | Hard limit on results per search. |
| `COLLECTOR_TIMEOUT_SECONDS` | `120` | A search running longer than this fails (partial results kept). |
| `MAX_CONCURRENT_JOBS` | `3` | How many searches can run at once. |
| `CORS_ORIGINS` | `http://localhost:3000` | Browser origin(s) allowed to call the API. |

### Frontend — `frontend/.env.local`

| Setting | Default | What it does |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL the browser calls. |

---

## Running with Docker (optional)

If you have [Docker](https://docs.docker.com/get-docker/) with Compose v2.24+, you can run both
parts with one command from the project root:

```bash
docker compose up --build
```

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>

To use the live 2GIS source with Docker, put your key in `backend/.env` first (it is picked up
automatically), then run the command above.

---

## Running the tests

### Backend tests

```bash
cd backend
# activate the venv first (see setup)
python -m pytest                      # everything (briefly launches a headless browser)
python -m pytest -m "not playwright"  # faster subset, no browser
```

### End-to-end browser tests

These drive the real dashboard in a browser. Run them from the project root. They will reuse the
servers if they're already running on ports 3000/8000, or start them automatically if not:

```bash
backend/.venv/Scripts/python -m pytest e2e      # Windows
backend/.venv/bin/python -m pytest e2e          # macOS / Linux
```

### Frontend checks

```bash
cd frontend
npm run lint
npm run build
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **Dashboard says "Can't reach the server"** | Make sure the backend terminal is running. The page retries automatically every few seconds. |
| **`pip install` fails** | Use Python 3.12 (`py -3.12 -m venv .venv` on Windows), then reinstall. |
| **"2GIS (live API)" isn't in the source list** | Set both `ENABLE_LIVE_COLLECTOR=true` and `TWOGIS_API_KEY` in `backend/.env`, then restart the backend. |
| **2GIS results have no phone numbers** | Your 2GIS key isn't licensed for contact data. Names/addresses/hours still work; a contact-data key is needed for phones. |
| **Local test page source fails** | Run `playwright install chromium` inside the backend venv. |
| **Port already in use** | Something else is using 3000 or 8000. Stop it, or change the port (`--port` for the backend; edit `NEXT_PUBLIC_API_URL` accordingly). |
| **Changed a `.env` value but nothing happened** | Restart the server after changing environment files. |

---

## Project structure

```
backend/      FastAPI API, data sources (collectors), processing, Excel export, tests
frontend/     Next.js dashboard (search form, results table, export button)
e2e/          End-to-end browser tests
docker-compose.yml
```

---

## Legal & responsible use

- The live 2GIS source uses the **official 2GIS Catalog API** with your own key — it does **not**
  scrape the website or bypass any protections.
- Use collected business data in line with the 2GIS API terms and with applicable marketing,
  privacy and telemarketing laws in your region.
- Results are limited to what the source makes available; complete coverage isn't guaranteed.
