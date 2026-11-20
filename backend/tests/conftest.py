import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import job_manager


@pytest.fixture(autouse=True)
def _live_collector_off_by_default(monkeypatch):
    # Keep tests independent of the developer's local .env (which may enable the live
    # 2GIS source). Tests that exercise the live source opt in via their own monkeypatch.
    monkeypatch.setattr(settings, "enable_live_collector", False)
    monkeypatch.setattr(settings, "twogis_api_key", "")


@pytest.fixture
def client():
    # The context manager keeps one event loop alive for the whole test, so background
    # job tasks keep running between requests, and runs lifespan shutdown afterwards.
    with TestClient(app) as c:
        yield c
    job_manager.clear()
