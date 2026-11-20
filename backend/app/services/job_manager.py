"""In-memory job store and background job runner (MVP).

Each job runs its collector as an asyncio task on the server's event loop:
- results are cleaned/deduplicated incrementally, so progress is live;
- collection stops at ``max_results`` unique records (capped by MAX_RESULTS_CAP);
- the whole run is bounded by COLLECTOR_TIMEOUT_SECONDS;
- jobs can be cancelled; partial results are kept on cancel, timeout and failure;
- errors shown to users are short and safe - full tracebacks go to the server log only.

Jobs live in process memory and are lost on restart (acceptable for the MVP, per spec §7).
"""
import asyncio
import logging
import uuid
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.collectors.base import BaseCollector, CollectorError
from app.collectors.registry import get_collector
from app.config import settings
from app.models.schemas import BusinessRecord, JobCreate, JobInfo, JobStatus
from app.services.processing import ListingCleaner, clean_text

logger = logging.getLogger(__name__)

MAX_STORED_JOBS = 100  # oldest finished jobs are evicted beyond this

TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED})


class TooManyJobsError(RuntimeError):
    """Raised when MAX_CONCURRENT_JOBS jobs are already running."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(eq=False)
class Job:
    id: str
    category: str
    location: str
    max_results: int
    collector: BaseCollector
    status: JobStatus = JobStatus.RUNNING
    error: str | None = None
    cleaner: ListingCleaner = field(default_factory=ListingCleaner)
    raw_count: int = 0
    created_at: datetime = field(default_factory=_now)
    finished_at: datetime | None = None
    task: asyncio.Task | None = field(default=None, repr=False)

    @property
    def records(self) -> list[BusinessRecord]:
        return self.cleaner.records

    @property
    def is_finished(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def finish(self, status: JobStatus, error: str | None = None) -> None:
        self.status = status
        self.error = error
        self.finished_at = _now()


_jobs: dict[str, Job] = {}


# --- public API ------------------------------------------------------------

def create_job(req: JobCreate) -> Job:
    """Validate the source and start a job. Must be called from within the running event loop.

    Raises ValueError (unknown source), PermissionError (source disabled) or TooManyJobsError.
    """
    collector = get_collector(req.source)
    return start_job(collector, req.category, req.location, req.max_results)


def start_job(
    collector: BaseCollector, category: str, location: str, max_results: int | None = None
) -> Job:
    """Start a job with an already-constructed collector (also the injection point for tests)."""
    running = sum(1 for j in _jobs.values() if not j.is_finished)
    if running >= settings.max_concurrent_jobs:
        raise TooManyJobsError(
            f"{running} searches are already running. Please wait for one to finish."
        )

    cap = settings.max_results_cap
    job = Job(
        id=uuid.uuid4().hex,
        category=clean_text(category),
        location=clean_text(location),
        max_results=min(max_results or cap, cap),
        collector=collector,
    )
    _jobs[job.id] = job
    _evict_old_jobs()
    # Keep a reference on the job so the task is not garbage-collected mid-run.
    job.task = asyncio.get_running_loop().create_task(_run(job), name=f"job-{job.id}")
    job.task.add_done_callback(lambda task: _ensure_finished(job, task))
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def cancel_job(job_id: str) -> Job | None:
    """Request cancellation. Returns the job (or None if unknown); no-op if already finished."""
    job = _jobs.get(job_id)
    if job and not job.is_finished and job.task:
        job.task.cancel()
    return job


def to_info(job: Job) -> JobInfo:
    return JobInfo(
        job_id=job.id,
        status=job.status,
        collected=len(job.records),
        total_expected=job.max_results,
        export_allowed=job.collector.export_allowed,
        error=job.error,
    )


async def shutdown() -> None:
    """Cancel all running jobs and wait for them to wind down (called on app shutdown)."""
    tasks = [j.task for j in _jobs.values() if j.task and not j.task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def clear() -> None:
    """Drop all stored jobs (test helper). Does not cancel running tasks - use shutdown() first."""
    _jobs.clear()


# --- internals -------------------------------------------------------------

async def _collect(job: Job) -> None:
    # aclosing() guarantees the collector's cleanup (e.g. closing the browser) runs
    # as soon as we stop early, are cancelled, or time out.
    async with aclosing(
        job.collector.collect(job.category, job.location, job.max_results)
    ) as listings:
        async for listing in listings:
            job.raw_count += 1
            job.cleaner.add(listing)
            if len(job.records) >= job.max_results:
                break


async def _run(job: Job) -> None:
    try:
        await asyncio.wait_for(_collect(job), timeout=settings.collector_timeout_seconds)
    except asyncio.CancelledError:
        job.finish(JobStatus.CANCELLED, "Search was cancelled.")
        raise
    except asyncio.TimeoutError:
        job.finish(
            JobStatus.FAILED,
            f"Search timed out after {settings.collector_timeout_seconds} seconds. "
            f"{len(job.records)} result(s) were collected before the timeout.",
        )
    except CollectorError as exc:
        logger.warning("Job %s: collector %s reported: %s", job.id, job.collector.name, exc)
        job.finish(JobStatus.FAILED, str(exc))
    except Exception:
        logger.exception("Job %s failed (collector=%s)", job.id, job.collector.name)
        job.finish(
            JobStatus.FAILED,
            "The search failed due to an unexpected error with the data source. Please try again later.",
        )
    else:
        job.finish(JobStatus.COMPLETED)


def _ensure_finished(job: Job, task: asyncio.Task) -> None:
    """Safety net: a task cancelled before its first step never enters _run's handlers."""
    if job.is_finished:
        return
    if task.cancelled():
        job.finish(JobStatus.CANCELLED, "Search was cancelled.")
    else:
        job.finish(JobStatus.FAILED, "The search stopped unexpectedly.")


def _evict_old_jobs() -> None:
    excess = len(_jobs) - MAX_STORED_JOBS
    if excess <= 0:
        return
    finished = sorted((j for j in _jobs.values() if j.is_finished), key=lambda j: j.created_at)
    for job in finished[:excess]:
        del _jobs[job.id]
