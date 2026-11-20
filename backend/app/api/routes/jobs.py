"""Job endpoints (spec section 7).

POST /api/jobs                    - start a search job
GET  /api/jobs/{job_id}           - status, totals, errors
GET  /api/jobs/{job_id}/results   - cleaned records
GET  /api/jobs/{job_id}/export    - .xlsx download (only if source permits export)
"""
from fastapi import APIRouter

router = APIRouter()

# TODO (Phase 1/4): implement using services.job_manager and services.exporter
