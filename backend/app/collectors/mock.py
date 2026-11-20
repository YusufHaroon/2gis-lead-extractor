"""Mock collector returning placeholder sample records (Phase 1)."""
from app.collectors.base import BaseCollector, RawListing


class MockCollector(BaseCollector):
    name = "mock"
    export_allowed = True

    async def collect(self, category, location, max_results):
        # TODO: yield placeholder RawListing objects
        return
        yield  # makes this an async generator
