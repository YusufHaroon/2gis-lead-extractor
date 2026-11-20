"""Browser end-to-end tests for the dashboard.

Uses servers already running on the default ports (frontend :3000, backend :8000) when they
respond; otherwise starts them for the session and stops them afterwards.
Run with the backend's virtualenv (it has Playwright):  backend/.venv/Scripts/python -m pytest e2e
"""
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_URL = os.environ.get("E2E_FRONTEND_URL", "http://localhost:3000")
API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")
STARTUP_TIMEOUT_S = 120


def _up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def _spawn(cmd: list[str], cwd: Path) -> subprocess.Popen:
    kwargs: dict = {"cwd": cwd, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def _kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":  # npm/next spawn child processes; kill the whole tree
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(15)


def _wait_for(url: str, proc: subprocess.Popen, name: str) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        if _up(url):
            return
        if proc.poll() is not None:
            raise RuntimeError(f"{name} exited during startup (code {proc.returncode})")
        time.sleep(0.5)
    raise RuntimeError(f"{name} did not start within {STARTUP_TIMEOUT_S}s")


@pytest.fixture(scope="session")
def servers():
    started: list[subprocess.Popen] = []
    try:
        if not _up(f"{API_URL}/health"):
            port = API_URL.rsplit(":", 1)[-1]
            proc = _spawn([sys.executable, "-m", "uvicorn", "app.main:app", "--port", port], ROOT / "backend")
            started.append(proc)
            _wait_for(f"{API_URL}/health", proc, "backend")
        if not _up(FRONTEND_URL):
            npm = shutil.which("npm")
            if not npm:
                pytest.skip("npm not found - start the frontend manually or install Node.js")
            port = FRONTEND_URL.rsplit(":", 1)[-1]
            proc = _spawn([npm, "run", "dev", "--", "-p", port], ROOT / "frontend")
            started.append(proc)
            _wait_for(FRONTEND_URL, proc, "frontend")
        yield {"frontend": FRONTEND_URL, "api": API_URL}
    finally:
        for proc in reversed(started):
            _kill_tree(proc)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, servers):
    context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    p = context.new_page()
    p.set_default_timeout(15_000)
    yield p
    context.close()
