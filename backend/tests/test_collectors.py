"""Tests for collectors."""
import asyncio

import pytest

from app.collectors.mock import POOL_SIZE, MockCollector
from app.collectors.registry import get_collector
from app.services.processing import clean_listings


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


def test_mock_respects_max_results():
    assert len(_collect(MockCollector(delay_seconds=0), max_results=5)) == 5


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
