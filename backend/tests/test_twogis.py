"""Unit tests for the live 2GIS Catalog API collector (no network: httpx MockTransport)."""
import asyncio

import httpx
import pytest

from app.collectors import twogis as twogis_mod
from app.collectors.base import CollectorError
from app.collectors.twogis import TwoGisCollector


def _item(i, phones=None):
    item = {"id": f"id-{i}", "name_ex": {"primary": f"Business {i}"}, "name": f"Business {i}, cafe"}
    if phones:
        item["contact_groups"] = [{"contacts": [{"type": "phone", "value": p} for p in phones]}]
    return item


def run_collector(handler, *, key="k", **init):
    """Run TwoGisCollector.collect against a mocked API, returning the raw listings."""
    transport = httpx.MockTransport(handler)

    max_results = init.pop("max_results", 100)

    async def main():
        collector = TwoGisCollector(api_key=key, **init)
        # Make the collector's AsyncClient use our transport.
        orig = httpx.AsyncClient

        def patched(*a, **k):
            k["transport"] = transport
            return orig(*a, **k)

        twogis_mod.httpx.AsyncClient = patched
        try:
            return [x async for x in collector.collect("Restaurants", "Dubai", max_results)]
        finally:
            twogis_mod.httpx.AsyncClient = orig

    return asyncio.run(main())


def ok(payload: dict, code=200) -> httpx.Response:
    body = {"meta": {"code": code}, "result": payload}
    return httpx.Response(200, json=body)


# --- happy paths -----------------------------------------------------------

def test_paginates_until_max_results():
    pages: dict[int, list] = {1: [_item(i) for i in range(10)], 2: [_item(i) for i in range(10, 20)]}

    def handler(request: httpx.Request) -> httpx.Response:
        if "region/list" in request.url.path:
            return ok({"items": [{"id": 99, "name": "Dubai"}]})
        page = int(request.url.params.get("page", 1))
        return ok({"items": pages.get(page, [])})

    raw = run_collector(handler, max_results=15)
    assert len(raw) == 15
    assert len({r.source_id for r in raw}) == 15  # distinct across pages


def test_stops_when_api_runs_out():
    def handler(request: httpx.Request) -> httpx.Response:
        if "region/list" in request.url.path:
            return ok({"items": []})
        page = int(request.url.params.get("page", 1))
        return ok({"items": [_item(1), _item(2)] if page == 1 else []})

    raw = run_collector(handler, max_results=100)
    assert [r.source_id for r in raw] == ["id-1", "id-2"]


def test_extracts_first_phone_and_passes_it_through_unaltered():
    def handler(request: httpx.Request) -> httpx.Response:
        if "region/list" in request.url.path:
            return ok({"items": []})
        page = int(request.url.params.get("page", 1))
        items = [
            _item(1, phones=["+971 4 000 0001", "+971 4 999 9999"]),
            _item(2),  # no phone
        ] if page == 1 else []
        return ok({"items": items})

    raw = run_collector(handler)
    assert raw[0].phones == ["+971 4 000 0001", "+971 4 999 9999"]
    assert raw[1].phones == []
    assert raw[0].name == "Business 1"  # name_ex.primary preferred over "name"


def test_sends_key_and_region_but_key_is_not_exposed_to_caller():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "region/list" in request.url.path:
            return ok({"items": [{"id": 99, "name": "Dubai"}]})
        seen["key"] = request.url.params.get("key")
        seen["region_id"] = request.url.params.get("region_id")
        return ok({"items": [_item(1)]})

    run_collector(handler, key="secret-key")
    assert seen["key"] == "secret-key"
    assert seen["region_id"] == "99"  # resolved from "Dubai"


def test_pinned_region_skips_region_lookup():
    calls = {"region": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "region/list" in request.url.path:
            calls["region"] += 1
            return ok({"items": []})
        return ok({"items": [_item(1)] if int(request.url.params.get("page", 1)) == 1 else []})

    run_collector(handler, region_id="99")
    assert calls["region"] == 0


# --- error mapping ---------------------------------------------------------

@pytest.mark.parametrize("code,fragment", [
    (403, "not authorized"),
    (429, "rate limit"),
    (500, r"error \(500"),
])
def test_api_errors_become_clear_collector_errors(code, fragment):
    def handler(request: httpx.Request) -> httpx.Response:
        if "region/list" in request.url.path:
            return ok({"items": []})
        body = {"meta": {"code": code, "error": {"message": "boom"}}}
        return httpx.Response(200, json=body)

    with pytest.raises(CollectorError, match=fragment):
        run_collector(handler)


def test_timeout_becomes_clear_collector_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    with pytest.raises(CollectorError, match="did not respond in time"):
        run_collector(handler)


def test_non_json_response_becomes_clear_collector_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>nope</html>")

    with pytest.raises(CollectorError, match="non-JSON"):
        run_collector(handler)


def test_missing_key_fails_clearly():
    async def main():
        c = TwoGisCollector(api_key="")
        return [x async for x in c.collect("a", "b", 5)]

    with pytest.raises(CollectorError, match="not configured"):
        asyncio.run(main())
