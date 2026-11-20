"""Playwright collector against the local sample pages in backend/fixtures (Phase 2).

This is the reference implementation for a browser-based collector. All selectors and
navigation for this "site" live in this module only. A live collector should follow the
same shape: open the listing page, read only *visible* listing data, follow pagination up
to a page limit, stop once ``max_results`` distinct businesses have been seen, and always
close the browser.

The fixture is static, so ``category`` is not used for filtering; ``location`` is attached to
each listing so name + location deduplication works for listings without an id.
"""
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.collectors.base import BaseCollector, CollectorError, RawListing
from app.collectors.threaded import iterate_in_thread
from app.services.processing import dedupe_key

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
START_PAGE = FIXTURES_DIR / "sample_listings.html"

# --- site-specific selectors (keep them here only) -------------------------
LISTINGS_CONTAINER = "#listings"
LISTING_ITEM = "li.listing"
NEXT_PAGE_LINK = "a.next"

# Runs in the page: returns plain data for every listing, keeping only phones that are
# actually rendered (hidden/display:none numbers are not "publicly displayed").
EXTRACT_LISTINGS_JS = """
els => els.map(el => {
  const visible = n => (typeof n.checkVisibility === "function" ? n.checkVisibility() : true);
  const nameEl = el.querySelector(".name");
  return {
    id: el.dataset.id ?? null,
    name: nameEl ? nameEl.textContent : "",
    phones: [...el.querySelectorAll(".phone")].filter(visible).map(p => p.textContent),
  };
})
"""

MAX_PAGES = 10            # hard stop on pagination, in case of a link loop
NAVIGATION_TIMEOUT_MS = 15_000
SELECTOR_TIMEOUT_MS = 5_000


class LocalFixtureCollector(BaseCollector):
    name = "local_fixture"
    label = "Local test page (Playwright)"
    export_allowed = True

    def __init__(self, start_url: str | None = None, headless: bool = True):
        self.start_url = start_url or START_PAGE.as_uri()
        self.headless = headless

    async def collect(self, category, location, max_results):
        # The browser runs on its own loop/thread so this works under any server event loop
        # (see app/collectors/threaded.py for the Windows background).
        async for listing in iterate_in_thread(
            lambda: self._collect(category, location, max_results),
            thread_name=f"collector-{self.name}",
        ):
            yield listing

    async def _collect(self, category, location, max_results):
        seen = set()
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                page.set_default_timeout(SELECTOR_TIMEOUT_MS)
                url: str | None = self.start_url

                for _ in range(MAX_PAGES):
                    if url is None:
                        break
                    await self._open(page, url)
                    rows = await page.eval_on_selector_all(LISTING_ITEM, EXTRACT_LISTINGS_JS)

                    for row in rows:
                        listing = RawListing(
                            name=row["name"],
                            phones=row["phones"],
                            source_id=row["id"],
                            location=location,
                        )
                        if len(seen) >= max_results:
                            return
                        seen.add(dedupe_key(listing))
                        yield listing

                    url = await self._next_page_url(page)
            finally:
                await browser.close()

    @staticmethod
    async def _open(page, url: str) -> None:
        try:
            await page.goto(url, timeout=NAVIGATION_TIMEOUT_MS)
        except PlaywrightTimeoutError as exc:
            raise CollectorError("The listing page took too long to load.") from exc
        except PlaywrightError as exc:
            raise CollectorError("The listing page could not be opened.") from exc
        try:
            await page.wait_for_selector(LISTINGS_CONTAINER, state="attached")
        except PlaywrightTimeoutError as exc:
            # The page loaded but doesn't look like a listing page any more.
            raise CollectorError(
                "The listing page layout was not recognised. The source may have changed."
            ) from exc

    @staticmethod
    async def _next_page_url(page) -> str | None:
        link = page.locator(NEXT_PAGE_LINK).first
        if await link.count() == 0:
            return None
        href = await link.get_attribute("href")
        if not href:
            return None
        # Resolve relative links against the current page, as the browser would.
        return await page.evaluate("href => new URL(href, location.href).href", href)
