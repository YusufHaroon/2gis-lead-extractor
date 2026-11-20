"""End-to-end tests for the /api/jobs endpoints using the mock collector."""
import io
import time

import pytest
from openpyxl import load_workbook

from app.collectors.mock import POOL_SIZE, MockCollector
from app.config import settings

TERMINAL = {"completed", "failed", "cancelled"}


@pytest.fixture(autouse=True)
def _fast_mock(monkeypatch):
    monkeypatch.setattr(MockCollector, "delay_seconds", 0)
    monkeypatch.setattr(settings, "max_concurrent_jobs", 3)
    monkeypatch.setattr(settings, "max_results_cap", 200)


@pytest.fixture
def slow_mock(monkeypatch):
    """Make mock jobs run long enough to observe/cancel them mid-run."""
    monkeypatch.setattr(MockCollector, "delay_seconds", 0.5)


def start(client, **overrides):
    body = {"category": "Restaurants", "location": "Dubai", "source": "mock", **overrides}
    return client.post("/api/jobs", json=body)


def wait_until_done(client, job_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = client.get(f"/api/jobs/{job_id}").json()
        if info["status"] in TERMINAL:
            return info
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


# --- happy path ------------------------------------------------------------

def test_full_job_lifecycle(client):
    r = start(client)
    assert r.status_code == 202
    created = r.json()
    assert created["status"] == "running"
    assert created["export_allowed"] is True

    info = wait_until_done(client, created["job_id"])
    assert info["status"] == "completed"
    assert info["collected"] == POOL_SIZE
    assert info["error"] is None

    results = client.get(f"/api/jobs/{created['job_id']}/results").json()
    assert len(results) == POOL_SIZE
    assert set(results[0]) == {"business_name", "phone_number"}
    assert any(r["phone_number"] is None for r in results)

    export = client.get(f"/api/jobs/{created['job_id']}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert 'filename="leads-restaurants-dubai.xlsx"' in export.headers["content-disposition"]

    ws = load_workbook(io.BytesIO(export.content)).active
    assert [c.value for c in ws[1]] == ["Business Name", "Phone Number"]
    assert ws.max_column == 2
    assert ws.max_row == POOL_SIZE + 1


def test_default_source_is_used_when_omitted(client):
    r = client.post("/api/jobs", json={"category": "Hotels", "location": "Dubai"})
    assert r.status_code == 202
    assert wait_until_done(client, r.json()["job_id"])["status"] == "completed"


def test_max_results_respected(client):
    job_id = start(client, max_results=5).json()["job_id"]
    info = wait_until_done(client, job_id)
    assert info["collected"] == 5
    assert info["total_expected"] == 5


def test_max_results_clamped_to_server_cap(client, monkeypatch):
    monkeypatch.setattr(settings, "max_results_cap", 4)
    job_id = start(client, max_results=10_000).json()["job_id"]
    assert wait_until_done(client, job_id)["collected"] == 4


def test_results_available_while_running(client, slow_mock):
    job_id = start(client).json()["job_id"]
    r = client.get(f"/api/jobs/{job_id}/results")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    client.post(f"/api/jobs/{job_id}/cancel")


# --- validation and source errors -----------------------------------------

@pytest.mark.parametrize(
    "body",
    [
        {"category": "", "location": "Dubai"},
        {"category": "   ", "location": "Dubai"},
        {"category": "Hotels", "location": ""},
        {"category": "Hotels"},
        {"category": "x" * 101, "location": "Dubai"},
        {"category": "Hotels", "location": "Dubai", "max_results": 0},
        {"category": "Hotels", "location": "Dubai", "max_results": "lots"},
    ],
)
def test_invalid_payload_rejected(client, body):
    assert client.post("/api/jobs", json=body).status_code == 422


def test_unknown_source_is_400(client):
    r = start(client, source="nope")
    assert r.status_code == 400
    assert "Unknown source" in r.json()["detail"]


def test_live_source_disabled_is_403(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_live_collector", False)
    assert start(client, source="twogis").status_code == 403


def test_too_many_running_jobs_is_429(client, slow_mock, monkeypatch):
    monkeypatch.setattr(settings, "max_concurrent_jobs", 1)
    first = start(client).json()["job_id"]
    assert start(client).status_code == 429
    client.post(f"/api/jobs/{first}/cancel")


# --- unknown jobs ----------------------------------------------------------

@pytest.mark.parametrize("suffix", ["", "/results", "/export"])
def test_unknown_job_is_404(client, suffix):
    assert client.get(f"/api/jobs/does-not-exist{suffix}").status_code == 404


def test_cancel_unknown_job_is_404(client):
    assert client.post("/api/jobs/does-not-exist/cancel").status_code == 404


# --- cancel ----------------------------------------------------------------

def test_cancel_running_job(client, slow_mock):
    job_id = start(client).json()["job_id"]
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 200
    info = wait_until_done(client, job_id)
    assert info["status"] == "cancelled"
    assert info["error"] == "Search was cancelled."


def test_cancel_finished_job_is_409(client):
    job_id = start(client, max_results=1).json()["job_id"]
    wait_until_done(client, job_id)
    assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 409


# --- export rules ----------------------------------------------------------

def test_export_while_running_is_409(client, slow_mock):
    job_id = start(client).json()["job_id"]
    r = client.get(f"/api/jobs/{job_id}/export")
    assert r.status_code == 409
    assert "running" in r.json()["detail"]
    client.post(f"/api/jobs/{job_id}/cancel")


def test_export_of_cancelled_job_is_409(client, slow_mock):
    job_id = start(client).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/cancel")
    wait_until_done(client, job_id)
    assert client.get(f"/api/jobs/{job_id}/export").status_code == 409


def test_export_blocked_when_source_does_not_permit(client, monkeypatch):
    monkeypatch.setattr(MockCollector, "export_allowed", False)
    created = start(client).json()
    assert created["export_allowed"] is False
    wait_until_done(client, created["job_id"])
    r = client.get(f"/api/jobs/{created['job_id']}/export")
    assert r.status_code == 403
    assert "not permitted" in r.json()["detail"]


def test_export_filename_is_sanitized(client):
    job_id = start(client, category='../"evil"', location="Dubai, UAE", max_results=1).json()["job_id"]
    wait_until_done(client, job_id)
    cd = client.get(f"/api/jobs/{job_id}/export").headers["content-disposition"]
    assert cd == 'attachment; filename="leads-evil-dubai-uae.xlsx"'


# --- local fixture source end-to-end (Playwright) --------------------------

@pytest.mark.playwright
def test_local_fixture_job_end_to_end(client):
    created = start(client, source="local_fixture")
    assert created.status_code == 202
    info = wait_until_done(client, created.json()["job_id"], timeout=60)
    assert info["status"] == "completed", info
    assert info["collected"] == 6

    results = client.get(f"/api/jobs/{info['job_id']}/results").json()
    assert results[1] == {"business_name": "Example Business B", "phone_number": None}

    ws = load_workbook(io.BytesIO(client.get(f"/api/jobs/{info['job_id']}/export").content)).active
    assert ws.max_row == 7 and ws.max_column == 2


@pytest.mark.playwright
def test_local_fixture_job_can_be_cancelled(client):
    job_id = start(client, source="local_fixture").json()["job_id"]
    client.post(f"/api/jobs/{job_id}/cancel")
    info = wait_until_done(client, job_id, timeout=60)
    assert info["status"] in {"cancelled", "completed"}  # it may finish before the cancel lands


# --- sources ---------------------------------------------------------------

def test_sources_lists_all_with_flags(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_live_collector", False)
    monkeypatch.setattr(settings, "default_collector", "mock")
    sources = {s["name"]: s for s in client.get("/api/sources").json()}
    assert set(sources) == {"mock", "local_fixture", "twogis"}
    assert sources["mock"] == {
        "name": "mock", "label": "Mock data (placeholder)",
        "enabled": True, "export_allowed": True, "is_default": True,
    }
    assert sources["twogis"]["enabled"] is False
    assert sources["twogis"]["export_allowed"] is True  # export rights confirmed by the owner


def test_sources_reflect_live_switch(client, monkeypatch):
    monkeypatch.setattr(settings, "enable_live_collector", True)
    monkeypatch.setattr(settings, "twogis_api_key", "test-key")
    sources = {s["name"]: s for s in client.get("/api/sources").json()}
    assert sources["twogis"]["enabled"] is True


def test_live_source_hidden_without_api_key(client, monkeypatch):
    # Switched on but no key configured -> still unavailable.
    monkeypatch.setattr(settings, "enable_live_collector", True)
    monkeypatch.setattr(settings, "twogis_api_key", "")
    sources = {s["name"]: s for s in client.get("/api/sources").json()}
    assert sources["twogis"]["enabled"] is False
    assert start(client, source="twogis").status_code == 403


# --- QA: empty, timeout and live-export acceptance cases (spec Phase 5) ----

@pytest.mark.playwright
def test_empty_results_complete_with_header_only_export(client, tmp_path, monkeypatch):
    from app.collectors import local_fixture

    empty = tmp_path / "empty.html"
    empty.write_text('<ul id="listings"></ul>')
    monkeypatch.setattr(local_fixture, "START_PAGE", empty)

    job_id = start(client, source="local_fixture").json()["job_id"]
    info = wait_until_done(client, job_id, timeout=60)
    assert info["status"] == "completed"
    assert info["collected"] == 0
    assert client.get(f"/api/jobs/{job_id}/results").json() == []

    ws = load_workbook(io.BytesIO(client.get(f"/api/jobs/{job_id}/export").content)).active
    assert [c.value for c in ws[1]] == ["Business Name", "Phone Number"]
    assert ws.max_row == 1


@pytest.mark.playwright
def test_layout_change_fails_job_with_clear_message(client, tmp_path, monkeypatch):
    from app.collectors import local_fixture

    changed = tmp_path / "changed.html"
    changed.write_text("<div class='redesigned'></div>")
    monkeypatch.setattr(local_fixture, "START_PAGE", changed)
    monkeypatch.setattr(local_fixture, "SELECTOR_TIMEOUT_MS", 300)

    info = wait_until_done(client, start(client, source="local_fixture").json()["job_id"], timeout=60)
    assert info["status"] == "failed"
    assert "layout was not recognised" in info["error"]


def test_timeout_fails_job_keeps_partial_results_and_blocks_export(client, monkeypatch):
    monkeypatch.setattr(MockCollector, "delay_seconds", 0.1)
    monkeypatch.setattr(settings, "collector_timeout_seconds", 0.5)

    job_id = start(client).json()["job_id"]
    info = wait_until_done(client, job_id)
    assert info["status"] == "failed"
    assert "timed out" in info["error"]
    assert 0 < info["collected"] < POOL_SIZE
    assert len(client.get(f"/api/jobs/{job_id}/results").json()) == info["collected"]
    assert client.get(f"/api/jobs/{job_id}/export").status_code == 409


def test_live_source_end_to_end_with_authorized_export(client, monkeypatch):
    """Live 2GIS (collection + export both authorized): job completes and Excel export works."""
    from app.collectors.base import RawListing
    from app.collectors.twogis import TwoGisCollector

    async def fake_collect(self, category, location, max_results):
        yield RawListing(name="Ocean Basket", phones=["+971 4 000 0001"], source_id="1")
        yield RawListing(name="Deccan Delight", phones=[], source_id="2")

    monkeypatch.setattr(settings, "enable_live_collector", True)
    monkeypatch.setattr(settings, "twogis_api_key", "test-key")
    monkeypatch.setattr(TwoGisCollector, "collect", fake_collect)

    created = start(client, source="twogis").json()
    assert created["export_allowed"] is True
    info = wait_until_done(client, created["job_id"])
    assert info["status"] == "completed" and info["collected"] == 2

    r = client.get(f"/api/jobs/{created['job_id']}/export")
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content)).active
    assert [c.value for c in ws[1]] == ["Business Name", "Phone Number"]
    assert list(ws.iter_rows(min_row=2, values_only=True)) == [
        ("Ocean Basket", "+971 4 000 0001"),
        ("Deccan Delight", None),
    ]


def test_live_source_export_rights_are_granted():
    from app.collectors.twogis import TwoGisCollector

    assert TwoGisCollector.export_allowed is True


def test_live_source_misconfigured_fails_cleanly(client, monkeypatch):
    # Enabled with a key in the registry's eyes, but the collector sees no key at run time.
    from app.collectors.twogis import TwoGisCollector

    monkeypatch.setattr(settings, "enable_live_collector", True)
    monkeypatch.setattr(settings, "twogis_api_key", "present-for-registry")

    def no_key_init(self, *a, **k):
        self.api_key = ""
        self.base_url = "https://example.invalid"
        self.region_id = ""

    monkeypatch.setattr(TwoGisCollector, "__init__", no_key_init)
    info = wait_until_done(client, start(client, source="twogis").json()["job_id"])
    assert info["status"] == "failed"
    assert "not configured" in info["error"]
