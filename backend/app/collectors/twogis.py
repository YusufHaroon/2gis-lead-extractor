"""Live 2GIS collector via the official 2GIS Catalog API (Step 9).

Uses an authorized API key (server-side only) instead of scraping the website, so there is
no browser, no page-layout fragility and no CAPTCHA/anti-bot handling. All 2GIS-specific
request/response details live in this module only.

Disabled unless ENABLE_LIVE_COLLECTOR=true AND TWOGIS_API_KEY is set. Export is governed by
``export_allowed`` and must only be True when lead-list export rights are confirmed.

Docs: https://docs.2gis.com/en/api/search/places/overview
- GET /3.0/items          text/region search, paginated (page, page_size<=50)
- fields=items.contact_groups returns contact details *if the key is licensed for them*.
  Keys without contact-data access silently omit the field (no error), so phones come back
  blank. That is a key-licensing matter, not a bug in this collector.
"""
import asyncio

import httpx

from app.collectors.base import BaseCollector, CollectorError, RawListing
from app.config import settings

PAGE_SIZE = 10  # API maximum per page for this endpoint
MAX_PAGES = 50  # safety cap (<= 500 results) regardless of max_results
REQUEST_TIMEOUT = 20.0
PHONE_CONTACT_TYPES = {"phone"}


class TwoGisCollector(BaseCollector):
    name = "twogis"
    label = "2GIS (live API)"
    # Export rights confirmed by the account owner (2026-11-20). The API key must also be
    # licensed for contact data for phone numbers to be present.
    export_allowed = True

    def __init__(self, api_key: str | None = None, base_url: str | None = None, region_id: str | None = None):
        self.api_key = api_key if api_key is not None else settings.twogis_api_key
        self.base_url = (base_url or settings.twogis_api_base).rstrip("/")
        self.region_id = region_id if region_id is not None else settings.twogis_region_id

    async def collect(self, category, location, max_results):
        if not self.api_key:
            # Safety net; the registry normally hides this source until a key is configured.
            raise CollectorError("The 2GIS data source is not configured (missing API key).")
        query = " ".join(p for p in (category, location) if p).strip() or category
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            region_id = self.region_id or await self._resolve_region(client, location)
            seen = 0
            for page in range(1, MAX_PAGES + 1):
                if seen >= max_results:
                    return
                items = await self._search_page(client, query, region_id, page)
                if not items:
                    return  # no more results
                for item in items:
                    if seen >= max_results:
                        return
                    seen += 1
                    yield self._to_listing(item, location)

    # --- API calls ---------------------------------------------------------

    async def _request(self, client: httpx.AsyncClient, path: str, params: dict) -> dict:
        try:
            resp = await client.get(f"{self.base_url}{path}", params={**params, "key": self.api_key})
        except httpx.TimeoutException as exc:
            raise CollectorError("2GIS did not respond in time. Please try again.") from exc
        except httpx.HTTPError as exc:
            raise CollectorError("Could not reach the 2GIS service.") from exc

        body = self._parse(resp)
        code = body.get("meta", {}).get("code", resp.status_code)
        if code == 403:
            raise CollectorError("2GIS rejected the request (the API key may be invalid or not authorized).")
        if code == 404:
            return body  # "nothing found" is reported per-endpoint by the caller
        if code == 429:
            raise CollectorError("2GIS rate limit reached. Please wait a moment and try again.")
        if code >= 400:
            message = body.get("meta", {}).get("error", {}).get("message", "unknown error")
            raise CollectorError(f"2GIS returned an error ({code}: {message}).")
        return body

    @staticmethod
    def _parse(resp: httpx.Response) -> dict:
        try:
            return resp.json()
        except ValueError as exc:
            raise CollectorError("2GIS returned an unexpected (non-JSON) response.") from exc

    async def _resolve_region(self, client: httpx.AsyncClient, location: str) -> str | None:
        """Best-effort region id for the location; None lets the API search globally by text."""
        if not location:
            return None
        body = await self._request(client, "/2.0/region/list", {})
        wanted = location.strip().casefold()
        items = body.get("result", {}).get("items", [])
        for it in items:  # exact name match first
            if (it.get("name") or "").casefold() == wanted:
                return str(it.get("id"))
        for it in items:  # then substring either way (e.g. "Dubai" in "Dubai, UAE")
            name = (it.get("name") or "").casefold()
            if name and (name in wanted or wanted in name):
                return str(it.get("id"))
        return None

    async def _search_page(self, client: httpx.AsyncClient, query: str, region_id: str | None, page: int) -> list[dict]:
        params = {
            "q": query,
            "page": page,
            "page_size": PAGE_SIZE,
            "fields": "items.contact_groups,items.name_ex,items.address",
        }
        if region_id:
            params["region_id"] = region_id
        body = await self._request(client, "/3.0/items", params)
        if body.get("meta", {}).get("code") == 404:
            return []
        return body.get("result", {}).get("items", [])

    # --- mapping -----------------------------------------------------------

    def _to_listing(self, item: dict, location: str) -> RawListing:
        name = (item.get("name_ex") or {}).get("primary") or item.get("name") or ""
        return RawListing(
            name=name,
            phones=self._phones(item),
            source_id=str(item["id"]) if item.get("id") is not None else None,
            location=location,
        )

    @staticmethod
    def _phones(item: dict) -> list[str]:
        """First-available phones from contact_groups; numbers are passed through unaltered."""
        phones: list[str] = []
        for group in item.get("contact_groups", []) or []:
            for contact in group.get("contacts", []) or []:
                if contact.get("type") in PHONE_CONTACT_TYPES:
                    value = contact.get("value") or contact.get("text")
                    if value:
                        phones.append(value)
        return phones
