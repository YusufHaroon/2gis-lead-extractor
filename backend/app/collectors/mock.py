"""Mock collector returning placeholder sample records (Phase 1).

Data is clearly fake (``Example ...`` names, ``+971 4 000 ....`` numbers) and deliberately
includes the edge cases the processing layer must handle: listings without a phone,
listings with several phones, and a duplicate of an earlier listing.
"""
import asyncio

from app.collectors.base import BaseCollector, RawListing
from app.services.processing import clean_text

POOL_SIZE = 25  # unique placeholder businesses available per search


class MockCollector(BaseCollector):
    name = "mock"
    label = "Mock data (placeholder)"
    export_allowed = True
    delay_seconds: float = 0.2  # simulated latency per listing so progress is visible in the UI

    def __init__(self, delay_seconds: float | None = None):
        if delay_seconds is not None:
            self.delay_seconds = delay_seconds

    def _listings(self, category: str, location: str):
        category = clean_text(category) or "Business"
        location = clean_text(location)
        for i in range(1, POOL_SIZE + 1):
            if i % 4 == 0:
                phones: list[str] = []  # no public phone -> blank cell
            elif i % 5 == 0:
                phones = [f"+971 4 000 {i:04d}", f"+971 4 999 {i:04d}"]  # only the first is kept
            else:
                phones = [f"+971 4 000 {i:04d}"]
            yield RawListing(
                name=f"Example {category} {i}",
                phones=phones,
                source_id=f"mock-{i}",
                location=location,
            )
            if i == 3:
                # Same business seen twice (e.g. on two result pages) -> removed by dedupe.
                yield RawListing(
                    name=f"Example {category} 1",
                    phones=["+971 4 000 0001"],
                    source_id="mock-1",
                    location=location,
                )

    async def collect(self, category, location, max_results):
        seen_ids: set[str] = set()  # max_results counts distinct businesses, not raw listings
        for listing in self._listings(category, location):
            if len(seen_ids) >= max_results:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            seen_ids.add(listing.source_id)
            yield listing
