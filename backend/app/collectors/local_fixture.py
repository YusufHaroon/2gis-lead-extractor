"""Playwright collector against the local sample page in backend/fixtures (Phase 2)."""
from app.collectors.base import BaseCollector, RawListing


class LocalFixtureCollector(BaseCollector):
    name = "local_fixture"
    export_allowed = True

    async def collect(self, category, location, max_results):
        # TODO: launch Chromium, open fixtures/sample_listings.html, parse listings
        return
        yield  # makes this an async generator
