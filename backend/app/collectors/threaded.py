"""Run an async generator on its own event loop in a dedicated thread.

Why: Playwright launches the browser as a subprocess, which needs an event loop that
supports subprocesses. On Windows, uvicorn (e.g. with ``--reload``) may run on a
SelectorEventLoop, which does not - Chromium then fails to start with NotImplementedError.
Running the browser on a private loop (Proactor on Windows) works with any server loop and
also keeps browser work off the API's event loop.

Contract of :func:`iterate_in_thread`:
- items are forwarded to the caller's loop through a small bounded queue (backpressure);
- exceptions raised by the producer are re-raised in the caller;
- when the caller stops early, is cancelled or times out, the producer is cancelled and
  its ``finally`` blocks (e.g. closing the browser) finish before control returns.
"""
import asyncio
import concurrent.futures
import sys
import threading
from collections.abc import AsyncIterator, Callable
from typing import TypeVar

T = TypeVar("T")

QUEUE_SIZE = 16
CLEANUP_TIMEOUT_SECONDS = 15.0

_ITEM, _DONE, _ERROR = "item", "done", "error"


def _new_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()  # supports subprocesses on Windows
    return asyncio.new_event_loop()


async def iterate_in_thread(
    factory: Callable[[], AsyncIterator[T]], thread_name: str = "collector"
) -> AsyncIterator[T]:
    caller_loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    worker_loop = _new_loop()
    task_ready: concurrent.futures.Future = concurrent.futures.Future()

    async def send(message) -> None:
        # Runs on the worker loop; the put itself happens on the caller's loop.
        await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(queue.put(message), caller_loop))

    async def produce() -> None:
        agen = factory()
        try:
            async for item in agen:
                await send((_ITEM, item))
            await send((_DONE, None))
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # forward collector errors to the caller
            await send((_ERROR, exc))
        finally:
            await agen.aclose()

    def thread_main() -> None:
        asyncio.set_event_loop(worker_loop)
        try:
            task = worker_loop.create_task(produce())
            task_ready.set_result(task)
            try:
                worker_loop.run_until_complete(task)
            except BaseException:
                pass  # cancellation, or an error already forwarded to the caller
            worker_loop.run_until_complete(worker_loop.shutdown_asyncgens())
        finally:
            worker_loop.close()

    thread = threading.Thread(target=thread_main, name=thread_name, daemon=True)
    thread.start()
    task: asyncio.Task = await asyncio.wrap_future(task_ready)

    try:
        while True:
            kind, value = await queue.get()
            if kind == _ITEM:
                yield value
            elif kind == _ERROR:
                raise value
            else:
                return
    finally:
        if not task.done():
            try:
                worker_loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # worker loop already closed - producer finished on its own
        # Wait for the producer's cleanup (browser close) without blocking the caller's loop.
        await asyncio.to_thread(thread.join, CLEANUP_TIMEOUT_SECONDS)
