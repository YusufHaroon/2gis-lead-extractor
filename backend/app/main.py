"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import health, jobs, sources
from app.services import job_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    # Cancel running collections cleanly (closes any open browsers) on shutdown.
    await job_manager.shutdown()


app = FastAPI(title="2GIS Business Lead Extractor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
