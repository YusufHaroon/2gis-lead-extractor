"""Tests for the in-memory job manager."""
import asyncio

import pytest

from app.collectors.base import BaseCollector, RawListing
from app.collectors.mock import POOL_SIZE, MockCollector
from app.config import settings
from app.models.schemas import JobCreate, JobStatus
from app.services import job_manager


# --- fake collectors -------------------------------------------------------

class EndlessCollector(BaseCollector):
    """Yields unique listings forever; records whether its cleanup ran."""
    name = "endless"
    export_allowed = False

    def __init__(self, delay: float = 0.01):
        self.delay = delay
        self.closed = False

    async def collect(self, category, location, max_results):
        i = 0
        try:
            while True:
                i += 1
                await asyncio.sleep(self.delay)
                yield RawListing(name=f"Example {i}", phones=[f"+971 4 000 {i:04d}"], source_id=str(i))
        finally:
            self.closed = True


class FailingCollector(BaseCollector):
    name = "failing"

    async def collect(self, category, location, max_results):
        yield RawListing(name="Example A", source_id="a")
        yield RawListing(name="Example B", source_id="b")
        raise RuntimeError("selector .listing not found - secret internal detail")


class DuplicateHeavyCollector(BaseCollector):
    """Every listing is yielded twice; checks the cap counts unique records."""
    name = "dupes"

    async def collect(self, category, location, max_results):
        for i in range(100):
            for _ in range(2):
                yield RawListing(name=f"Example {i}", source_id=str(i))


# --- helpers ---------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(settings, "max_results_cap", 200)
    monkeypatch.setattr(settings, "collector_timeout_seconds", 5)
    monkeypatch.setattr(settings, "max_concurrent_jobs", 3)
    job_manager.clear()
    yield
    job_manager.clear()


async def _wait(job):
    await asyncio.gather(job.task, return_exceptions=True)
    return job


def run(coro):
    return asyncio.run(coro)


# --- tests -----------------------------------------------------------------

def test_mock_job_completes_with_clean_records():
    async def scenario():
        job = job_manager.start_job(MockCollector(delay_seconds=0), "Hotels", "Dubai", 100)
        assert job.status is JobStatus.RUNNING
        return await _wait(job)

    job = run(scenario())
    assert job.status is JobStatus.COMPLETED
    assert job.error is None
    assert len(job.records) == POOL_SIZE  # duplicate removed
    assert job.finished_at is not None

    info = job_manager.to_info(job)
    assert info.collected == POOL_SIZE
    assert info.export_allowed is True
    assert info.total_expected == 100


def test_create_job_uses_registry_and_validates_source():
    async def scenario():
        with pytest.raises(ValueError):
            job_manager.create_job(JobCreate(category="Hotels", location="Dubai", source="nope"))
        with pytest.raises(PermissionError):
            job_manager.create_job(JobCreate(category="Hotels", location="Dubai", source="twogis"))
        job = job_manager.create_job(JobCreate(category="Hotels", location="Dubai", source="mock", max_results=3))
        job.collector.delay_seconds = 0
        return await _wait(job)

    job = run(scenario())
    assert job.status is JobStatus.COMPLETED
    assert job_manager.get_job(job.id) is job


def test_max_results_counts_unique_records():
    async def scenario():
        return await _wait(job_manager.start_job(DuplicateHeavyCollector(), "x", "y", 10))

    job = run(scenario())
    assert job.status is JobStatus.COMPLETED
    assert len(job.records) == 10
    assert job.raw_count == 19  # 10 unique + 9 duplicates seen before the 10th unique


def test_max_results_clamped_to_cap_and_stops_endless_source(monkeypatch):
    monkeypatch.setattr(settings, "max_results_cap", 7)

    async def scenario():
        collector = EndlessCollector(delay=0)
        job = job_manager.start_job(collector, "x", "y", 10_000)
        await _wait(job)
        return job, collector

    job, collector = run(scenario())
    assert job.max_results == 7
    assert len(job.records) == 7
    assert job.status is JobStatus.COMPLETED
    assert collector.closed  # generator closed promptly after early stop


def test_default_max_results_is_cap(monkeypatch):
    monkeypatch.setattr(settings, "max_results_cap", 12)

    async def scenario():
        return await _wait(job_manager.start_job(MockCollector(delay_seconds=0), "x", "y", None))

    assert run(scenario()).max_results == 12


def test_timeout_fails_job_and_keeps_partial_results(monkeypatch):
    monkeypatch.setattr(settings, "collector_timeout_seconds", 0.2)

    async def scenario():
        collector = EndlessCollector(delay=0.02)
        job = job_manager.start_job(collector, "x", "y", 200)
        await _wait(job)
        return job, collector

    job, collector = run(scenario())
    assert job.status is JobStatus.FAILED
    assert "timed out" in job.error
    assert 0 < len(job.records) < 200
    assert collector.closed


def test_cancel_marks_cancelled_and_keeps_partial_results():
    async def scenario():
        collector = EndlessCollector(delay=0.01)
        job = job_manager.start_job(collector, "x", "y", 200)
        await asyncio.sleep(0.1)
        assert job_manager.cancel_job(job.id) is job
        await _wait(job)
        return job, collector

    job, collector = run(scenario())
    assert job.status is JobStatus.CANCELLED
    assert len(job.records) > 0
    assert collector.closed


def test_cancel_before_task_starts_still_marks_cancelled():
    async def scenario():
        job = job_manager.start_job(EndlessCollector(), "x", "y", 200)
        job_manager.cancel_job(job.id)  # no await in between: task never ran a step
        return await _wait(job)

    job = run(scenario())
    assert job.status is JobStatus.CANCELLED
    assert job.is_finished


def test_cancel_finished_job_is_noop():
    async def scenario():
        job = await _wait(job_manager.start_job(MockCollector(delay_seconds=0), "x", "y", 3))
        job_manager.cancel_job(job.id)
        await asyncio.sleep(0)
        return job

    assert run(scenario()).status is JobStatus.COMPLETED


def test_cancel_unknown_job_returns_none():
    assert job_manager.cancel_job("does-not-exist") is None


def test_collector_error_fails_job_with_safe_message_and_partial_results():
    async def scenario():
        return await _wait(job_manager.start_job(FailingCollector(), "x", "y", 10))

    job = run(scenario())
    assert job.status is JobStatus.FAILED
    assert "secret internal detail" not in job.error
    assert len(job.records) == 2


def test_concurrent_job_limit(monkeypatch):
    monkeypatch.setattr(settings, "max_concurrent_jobs", 2)

    async def scenario():
        jobs = [job_manager.start_job(EndlessCollector(), "x", "y", 200) for _ in range(2)]
        with pytest.raises(job_manager.TooManyJobsError):
            job_manager.start_job(EndlessCollector(), "x", "y", 200)
        job_manager.cancel_job(jobs[0].id)
        await _wait(jobs[0])
        third = job_manager.start_job(EndlessCollector(), "x", "y", 200)  # slot freed
        await job_manager.shutdown()
        return [*jobs, third]

    assert all(j.status is JobStatus.CANCELLED for j in run(scenario()))


def test_shutdown_cancels_running_jobs():
    async def scenario():
        job = job_manager.start_job(EndlessCollector(), "x", "y", 200)
        await asyncio.sleep(0.05)
        await job_manager.shutdown()
        return job

    assert run(scenario()).status is JobStatus.CANCELLED


def test_old_finished_jobs_are_evicted(monkeypatch):
    monkeypatch.setattr(job_manager, "MAX_STORED_JOBS", 3)

    async def scenario():
        jobs = []
        for _ in range(5):
            jobs.append(await _wait(job_manager.start_job(MockCollector(delay_seconds=0), "x", "y", 1)))
        return jobs

    jobs = run(scenario())
    assert job_manager.get_job(jobs[0].id) is None
    assert job_manager.get_job(jobs[-1].id) is jobs[-1]
