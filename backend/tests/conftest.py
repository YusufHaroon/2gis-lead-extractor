import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import job_manager


@pytest.fixture
def client():
    # The context manager keeps one event loop alive for the whole test, so background
    # job tasks keep running between requests, and runs lifespan shutdown afterwards.
    with TestClient(app) as c:
        yield c
    job_manager.clear()
