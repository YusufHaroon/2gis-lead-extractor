# 2GIS Business Lead Extractor

Next.js + FastAPI + Playwright app that searches businesses by category and location
and exports **Business Name** and **Phone Number** (max one per business) to Excel.

## Structure
- `backend/`  - FastAPI API, collectors (mock / local fixture / live), processing, Excel export
- `frontend/` - Next.js + Tailwind dashboard

## Quick start (local)
```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
playwright install chromium
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. API docs: http://localhost:8000/docs

## Source permissions
The live 2GIS collector is disabled by default (`ENABLE_LIVE_COLLECTOR=false`).
Enable it only when collection and export are authorized. No CAPTCHA/anti-bot bypass,
proxy rotation or stealth techniques are used.
