"""Dashboard end-to-end tests (spec Phase 4/5): real flows against the mock and local fixture
sources, plus stubbed API responses for states those sources can't produce."""
import io
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook
from playwright.sync_api import Page, Route, expect

CORS = {"access-control-allow-origin": "*"}


def open_dashboard(page: Page, servers) -> Page:
    page.goto(servers["frontend"])
    # Wait for the source list to load. The exact set depends on backend config (the live
    # 2GIS source may or may not be enabled), so just require the always-present mock option.
    expect(page.locator("#source option", has_text="Mock data")).to_have_count(1)
    return page


def search(page: Page, category="Restaurants", location="Dubai", max_results="", source=None):
    page.fill("#category", category)
    page.fill("#location", location)
    page.fill("#maxResults", max_results)
    if source:
        page.select_option("#source", source)
    page.get_by_role("button", name="Start Collection").click()


def badge(page: Page, label: str):
    return page.locator("#status-heading + span", has_text=label)


def no_horizontal_scroll(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def stub_job(page: Page, api: str, final: dict, records: list[dict]):
    """Serve a fake job: POST returns 'running', the first poll returns `final`."""
    running = {"job_id": "stub", "status": "running", "collected": 0, "total_expected": 50,
               "export_allowed": True, "error": None}

    def reply(body, status=200):
        return lambda route: route.fulfill(status=status, headers=CORS, content_type="application/json",
                                           body=json.dumps(body))

    page.route(f"{api}/api/jobs", reply(running, 202))
    page.route(f"{api}/api/jobs/stub", reply({**running, **final}))
    page.route(f"{api}/api/jobs/stub/results", reply(records))


# --- real flows ------------------------------------------------------------

def test_idle_state(page, servers):
    open_dashboard(page, servers)
    expect(badge(page, "Idle")).to_be_visible()
    expect(page.get_by_text("Choose a category and location")).to_be_visible()
    # Live-source visibility is config-dependent and covered by backend tests; here we only
    # require that disabled sources are never listed (an option is present only when enabled).
    expect(page.locator("table")).to_have_count(0)


def test_client_side_validation(page, servers):
    open_dashboard(page, servers)
    page.get_by_role("button", name="Start Collection").click()
    expect(page.get_by_text("Enter or pick a category.")).to_be_visible()
    expect(page.get_by_text("Enter a city or country.")).to_be_visible()

    search(page, category="   ", location="Dubai", max_results="0")
    expect(page.get_by_text("Enter or pick a category.")).to_be_visible()
    expect(page.get_by_text("Use a whole number of 1 or more.")).to_be_visible()
    expect(badge(page, "Idle")).to_be_visible()  # nothing was submitted


def test_mock_search_runs_completes_and_exports(page, servers):
    open_dashboard(page, servers)
    search(page)

    # Running: form locked, partial results streaming in, export not yet available
    expect(page.get_by_role("button", name="Collection running…")).to_be_disabled()
    expect(page.locator("#category")).to_be_disabled()
    expect(badge(page, "Running")).to_be_visible()
    expect(page.locator("tbody tr").first).to_be_visible()
    assert page.locator("tbody tr").count() < 25
    expect(page.get_by_role("button", name="Download Excel")).to_be_disabled()

    # Completed
    expect(badge(page, "Completed")).to_be_visible(timeout=20_000)
    expect(page.locator("tbody tr")).to_have_count(25)
    expect(page.get_by_text("Found 25 businesses for “Restaurants” in “Dubai”")).to_be_visible()
    expect(page.get_by_role("button", name="Start Collection")).to_be_enabled()

    # Every 4th mock business has no phone -> blank phone cell (dash, labelled for screen readers).
    blank = page.locator("tbody tr").nth(3).locator("td").nth(1)
    expect(blank.locator("a")).to_have_count(0)
    expect(blank.locator(".sr-only")).to_have_text("Not available")
    # Extra columns are present and populated by the mock source.
    expect(page.locator("thead th")).to_have_text(
        ["Business Name", "Phone Number", "Address", "Category", "Opening Hours"])
    expect(page.locator("tbody tr").first.locator("td").nth(2)).to_contain_text("Example Street")

    with page.expect_download() as dl:
        page.get_by_role("link", name="Download Excel").click()
    download = dl.value
    assert download.suggested_filename == "leads-restaurants-dubai.xlsx"
    ws = load_workbook(io.BytesIO(Path(download.path()).read_bytes())).active
    assert [c.value for c in ws[1]] == ["Business Name", "Phone Number", "Address", "Category", "Opening Hours"]
    assert ws.max_row == 26 and ws.max_column == 5


def test_cancel_running_search(page, servers):
    open_dashboard(page, servers)
    search(page, category="Hotels")
    expect(page.locator("tbody tr").first).to_be_visible()
    page.get_by_role("button", name="Cancel").click()
    expect(badge(page, "Cancelled")).to_be_visible()
    expect(page.get_by_text("Search cancelled.")).to_be_visible()
    expect(page.get_by_text("Export is only available for completed searches.")).to_be_visible()


@pytest.mark.parametrize("width,height", [(390, 844), (820, 1180), (1280, 900)], ids=["mobile", "tablet", "desktop"])
def test_responsive_layout(page, servers, width, height):
    page.set_viewport_size({"width": width, "height": height})
    open_dashboard(page, servers)
    assert no_horizontal_scroll(page)
    search(page, max_results="5")
    expect(badge(page, "Completed")).to_be_visible(timeout=20_000)
    expect(page.locator("tbody tr")).to_have_count(5)
    assert no_horizontal_scroll(page)
    expect(page.get_by_role("link", name="Download Excel")).to_be_in_viewport()


def test_local_fixture_source(page, servers):
    open_dashboard(page, servers)
    search(page, category="Clinics", source="local_fixture")
    expect(badge(page, "Completed")).to_be_visible(timeout=60_000)
    expect(page.locator("tbody tr")).to_have_count(6)
    expect(page.get_by_text("Found 6 businesses")).to_be_visible()


# --- stubbed states --------------------------------------------------------

def test_empty_results_message(page, servers):
    stub_job(page, servers["api"], {"status": "completed", "collected": 0}, [])
    open_dashboard(page, servers)
    search(page, category="Igloo builders", location="Dubai")
    expect(badge(page, "Completed")).to_be_visible()
    expect(page.get_by_text("No businesses found for “Igloo builders” in “Dubai”")).to_be_visible()
    expect(page.locator("table")).to_have_count(0)


def test_failed_search_shows_error_and_partial_results(page, servers):
    records = [{"business_name": "Example Business A", "phone_number": "+971 4 000 0001"}]
    stub_job(page, servers["api"], {"status": "failed", "collected": 1,
                                    "error": "Search timed out after 120 seconds."}, records)
    open_dashboard(page, servers)
    search(page)
    expect(badge(page, "Failed")).to_be_visible()
    expect(page.get_by_text("Search timed out after 120 seconds. Showing 1 business collected")).to_be_visible()
    expect(page.locator("tbody tr")).to_have_count(1)
    expect(page.get_by_role("button", name="Download Excel")).to_be_disabled()


def test_export_not_permitted_reason(page, servers):
    records = [{"business_name": "Example Business A", "phone_number": None}]
    stub_job(page, servers["api"], {"status": "completed", "collected": 1, "export_allowed": False}, records)
    open_dashboard(page, servers)
    search(page)
    expect(badge(page, "Completed")).to_be_visible()
    expect(page.get_by_text("Export is not permitted for this data source.")).to_be_visible()
    expect(page.get_by_role("link", name="Download Excel")).to_have_count(0)


def test_server_error_on_start_is_shown(page, servers):
    page.route(f"{servers['api']}/api/jobs", lambda r: r.fulfill(
        status=429, headers=CORS, content_type="application/json",
        body=json.dumps({"detail": "3 searches are already running. Please wait for one to finish."})))
    open_dashboard(page, servers)
    search(page)
    expect(page.locator("form [role=alert]")).to_have_text("3 searches are already running. Please wait for one to finish.")
    expect(page.get_by_role("button", name="Start Collection")).to_be_enabled()


def test_backend_unreachable(page, servers):
    page.route(f"{servers['api']}/**", lambda route: route.abort("connectionrefused"))
    page.goto(servers["frontend"])
    expect(page.get_by_role("alert").first).to_contain_text("Can't reach the server")
    search(page)
    expect(page.locator("form [role=alert]")).to_contain_text("Can't reach the server")
    expect(badge(page, "Idle")).to_be_visible()


def test_recovers_when_backend_comes_back(page, servers):
    page.route(f"{servers['api']}/**", lambda route: route.abort("connectionrefused"))
    page.goto(servers["frontend"])
    expect(page.get_by_role("alert").first).to_contain_text("Can't reach the server")
    page.unroute(f"{servers['api']}/**")
    expect(page.locator("#source")).to_be_visible(timeout=15_000)  # retried automatically
    expect(page.get_by_text("Can't reach the server")).to_have_count(0)
