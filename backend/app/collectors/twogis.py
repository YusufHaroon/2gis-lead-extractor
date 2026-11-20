"""Live 2GIS website collector - DISABLED unless ENABLE_LIVE_COLLECTOR=true.

Enable only when collection, storage and lead-generation export are authorized.
Must not bypass CAPTCHAs, authentication, anti-bot controls or access restrictions.
All 2GIS selectors and navigation logic live in this module only.
"""
from app.collectors.base import BaseCollector, RawListing


class TwoGisCollector(BaseCollector):
    name = "twogis"
    export_allowed = False  # set True only with confirmed export rights

    async def collect(self, category, location, max_results):
        raise NotImplementedError("Live 2GIS collector is not implemented/enabled.")
        yield  # makes this an async generator
