"""Tests for the run-on-own-loop helper used by browser collectors (no Playwright needed)."""
import asyncio
import threading
from contextlib import aclosing

import pytest

from app.collectors.threaded import iterate_in_thread


def _collector_threads():
    return [t for t in threading.enumerate() if t.name.startswith("test-collector")]


async def _numbers(n, delay=0.0, log=None):
    try:
        for i in range(n):
            if delay:
                await asyncio.sleep(delay)
            yield i
    finally:
        if log is not None:
            log.append(("closed", threading.current_thread().name))


def test_forwards_all_items_in_order():
    async def scenario():
        return [x async for x in iterate_in_thread(lambda: _numbers(50), "test-collector")]

    assert asyncio.run(scenario()) == list(range(50))  # > QUEUE_SIZE exercises backpressure
    assert _collector_threads() == []


def test_producer_runs_on_a_different_thread():
    log = []

    async def scenario():
        return [x async for x in iterate_in_thread(lambda: _numbers(3, log=log), "test-collector-x")]

    asyncio.run(scenario())
    assert log == [("closed", "test-collector-x")]


def test_producer_error_is_reraised_and_cleaned_up():
    log = []

    async def failing():
        try:
            yield 1
            raise ValueError("boom")
        finally:
            log.append("closed")

    async def scenario():
        got = []
        with pytest.raises(ValueError, match="boom"):
            async for x in iterate_in_thread(failing, "test-collector"):
                got.append(x)
        return got

    assert asyncio.run(scenario()) == [1]
    assert log == ["closed"]
    assert _collector_threads() == []


def test_early_stop_cancels_producer_and_waits_for_cleanup():
    log = []

    async def scenario():
        async with aclosing(iterate_in_thread(lambda: _numbers(10_000, 0.001, log), "test-collector")) as it:
            async for x in it:
                if x == 3:
                    break
        # Cleanup must have completed by the time aclose() returns.
        return list(log)

    assert asyncio.run(scenario()) and log[0][0] == "closed"
    assert _collector_threads() == []


def test_caller_cancellation_stops_producer():
    log = []

    async def consume():
        async with aclosing(iterate_in_thread(lambda: _numbers(10_000, 0.01, log), "test-collector")) as it:
            async for _ in it:
                pass

    async def scenario():
        task = asyncio.create_task(consume())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert log and log[0][0] == "closed"
    assert _collector_threads() == []
