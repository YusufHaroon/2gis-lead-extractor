"""Tests for collectors."""
import asyncio

import pytest

from app.collectors import local_fixture
from app.collectors.base import CollectorError
from app.collectors.local_fixture import LocalFixtureCollector
from app.collectors.mock import POOL_SIZE, MockCollector
from app.collectors.registry import get_collector
from app.services.processing import clean_listings, dedupe_key


def _collect(collector, category="Restaurants", location="Dubai", max_results=100):
    async def run():
        return [item async for item in collector.collect(category, location, max_results)]

    return asyncio.run(run())


# --- mock collector --------------------------------------------------------

def test_mock_yields_placeholder_records():
    raw = _collect(MockCollector(delay_seconds=0))
    assert raw
    assert all(r.name.startswith("Example Restaurants") for r in raw)
    assert all(r.location == "Dubai" for r in raw)


@pytest.mark.parametrize("max_results", [1, 3, 4, 5, POOL_SIZE])
def test_mock_max_results_counts_distinct_businesses(max_results):
    # The duplicate yielded after item 3 must not use up the budget.
    raw = _collect(MockCollector(delay_seconds=0), max_results=max_results)
    assert len({r.source_id for r in raw}) == max_results
    assert len(clean_listings(raw)) == max_results


def test_mock_cleans_to_full_pool_with_edge_cases():
    records = clean_listings(_collect(MockCollector(delay_seconds=0)))
    assert len(records) == POOL_SIZE  # duplicate removed
    phones = [r.phone_number for r in records]
    assert None in phones  # some blanks
    assert all(p is None or p.startswith("+971 4 000") for p in phones)  # first phone kept


def test_mock_contains_a_duplicate_before_cleaning():
    raw = _collect(MockCollector(delay_seconds=0))
    ids = [r.source_id for r in raw]
    assert len(ids) != len(set(ids))


# --- registry --------------------------------------------------------------

def test_registry_returns_mock_by_default():
    assert isinstance(get_collector(None), MockCollector)


def test_registry_rejects_unknown_source():
    with pytest.raises(ValueError):
        get_collector("nope")


def test_registry_blocks_live_collector_when_disabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "enable_live_collector", False)
    with pytest.raises(PermissionError):
        get_collector("twogis")


# --- local fixture collector (Playwright + Chromium) ------------------------

FIXTURE_EXPECTED = [
    ("Example Business A", "+971 4 000 0001"),
    ("Example Business B", None),             # no phone on page
    ("Example Business C", "+971 4 000 0003"),  # two phones -> first; repeated on page 2
    ("Example Business D", "+971 4 000 0005"),  # messy whitespace in name
    ("Example Business E", "+971 4 000 0006"),  # hidden phone skipped; no id -> name dedupe
    ("Example Business F", None),             # whitespace-only + hidden phone -> blank
]


@pytest.mark.playwright
def test_fixture_collector_reads_both_pages_and_cleans_to_expected():
    raw = _collect(LocalFixtureCollector(), max_results=100)
    assert [(r.business_name, r.phone_number) for r in clean_listings(raw)] == FIXTURE_EXPECTED
    assert all(r.location == "Dubai" for r in raw)


@pytest.mark.playwright
def test_fixture_collector_never_returns_hidden_phones():
    raw = _collect(LocalFixtureCollector(), max_results=100)
    assert not any("999" in p for r in raw for p in r.phones)


@pytest.mark.playwright
@pytest.mark.parametrize("max_results", [2, 3, 4, 6])
def test_fixture_collector_max_results_counts_distinct_businesses(max_results):
    raw = _collect(LocalFixtureCollector(), max_results=max_results)
    assert len({dedupe_key(r) for r in raw}) == max_results
    assert len(clean_listings(raw)) == max_results


@pytest.mark.playwright
def test_fixture_collector_layout_change_is_a_clear_collector_error(tmp_path, monkeypatch):
    monkeypatch.setattr(local_fixture, "SELECTOR_TIMEOUT_MS", 300)
    page = tmp_path / "changed.html"
    page.write_text("<html><body><div class='new-layout'>Redesigned</div></body></html>")
    with pytest.raises(CollectorError, match="layout was not recognised"):
        _collect(LocalFixtureCollector(start_url=page.as_uri()))


@pytest.mark.playwright
def test_fixture_collector_missing_page_is_a_clear_collector_error(tmp_path):
    with pytest.raises(CollectorError, match="could not be opened"):
        _collect(LocalFixtureCollector(start_url=(tmp_path / "missing.html").as_uri()))


@pytest.mark.playwright
def test_fixture_collector_stops_on_pagination_loop(tmp_path, monkeypatch):
    monkeypatch.setattr(local_fixture, "MAX_PAGES", 3)
    page = tmp_path / "loop.html"
    page.write_text(
        '<ul id="listings"><li class="listing" data-id="1"><span class="name">Example Loop</span></li></ul>'
        '<a class="next" href="loop.html">Next</a>'
    )
    raw = _collect(LocalFixtureCollector(start_url=page.as_uri()), max_results=100)
    assert len(raw) == 3  # one listing per page visit, then the page limit stops it
    assert len(clean_listings(raw)) == 1
