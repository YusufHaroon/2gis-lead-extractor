"""Normalization, first-available phone selection and deduplication (Phase 3).

Rules from the spec:
- At most one publicly displayed phone per business; blank (None) when unavailable.
- Phone numbers are never guessed, fabricated or altered - only surrounding whitespace is trimmed.
- Duplicates are removed using the source identifier when available, otherwise a
  normalized name + location combination.
"""
import re
import unicodedata
from collections.abc import Iterable

from app.collectors.base import RawListing
from app.models.schemas import BusinessRecord

_WHITESPACE = re.compile(r"\s+")
_DIGIT = re.compile(r"\d")

DedupeKey = tuple[str, ...]


def clean_text(value: str | None) -> str:
    """Collapse runs of whitespace into single spaces and trim. Case is preserved."""
    if not value:
        return ""
    return _WHITESPACE.sub(" ", value).strip()


def normalize_name(value: str | None) -> str:
    """Comparison form of a name/location: Unicode-normalized, case-folded, whitespace-collapsed.

    Used only for building dedupe keys - never for displayed or exported values.
    """
    return clean_text(unicodedata.normalize("NFKC", value or "")).casefold()


def pick_first_phone(phones: Iterable[str | None] | None) -> str | None:
    """Return the first phone entry containing at least one digit, trimmed but otherwise unchanged."""
    for phone in phones or ():
        if not phone:
            continue
        candidate = phone.strip()
        if _DIGIT.search(candidate):
            return candidate
    return None


def dedupe_key(listing: RawListing) -> DedupeKey:
    """Stable identity for a listing: source id first, else normalized name + location."""
    source_id = (listing.source_id or "").strip()
    if source_id:
        return ("id", source_id)
    return ("name_location", normalize_name(listing.name), normalize_name(listing.location))


class ListingCleaner:
    """Incremental cleaner: feed raw listings one at a time, accumulate unique clean records.

    Lets a running job report an accurate unique count while the collector is still going.
    """

    def __init__(self) -> None:
        self._seen: set[DedupeKey] = set()
        self.records: list[BusinessRecord] = []

    def add(self, listing: RawListing) -> BusinessRecord | None:
        """Add a listing; return the new record, or None if it was nameless or a duplicate."""
        name = clean_text(listing.name)
        if not name:
            return None
        key = dedupe_key(listing)
        if key in self._seen:
            return None
        self._seen.add(key)
        record = BusinessRecord(
            business_name=name,
            phone_number=pick_first_phone(listing.phones),
            address=clean_text(listing.address) or None,
            category=clean_text(listing.category) or None,
            opening_hours=clean_text(listing.opening_hours) or None,
        )
        self.records.append(record)
        return record


def clean_listings(listings: Iterable[RawListing]) -> list[BusinessRecord]:
    """Convert raw listings to clean records: drop nameless entries, keep the first of each duplicate."""
    cleaner = ListingCleaner()
    for listing in listings:
        cleaner.add(listing)
    return cleaner.records
