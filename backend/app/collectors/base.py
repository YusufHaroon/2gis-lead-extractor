"""Collector interface shared by all data sources."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class RawListing:
    """A listing as read from the source, before cleanup."""
    name: str
    phones: list[str] = field(default_factory=list)
    source_id: str | None = None
    location: str | None = None


class CollectorError(Exception):
    """An expected collection failure whose message is safe to show to users
    (e.g. the page layout changed, or the source could not be reached)."""


class BaseCollector(ABC):
    name: str = "base"
    export_allowed: bool = False  # whether the source licence permits Excel export

    @abstractmethod
    def collect(self, category: str, location: str, max_results: int) -> AsyncIterator[RawListing]:
        """Yield raw listings, respecting max_results and source limits.

        ``max_results`` counts distinct businesses, not raw listings: a collector that sees
        the same business twice (e.g. on two result pages) must not count it twice, or the
        job would return fewer records than requested. Over-yielding is safe - the job
        manager dedupes and stops consuming once it has ``max_results`` unique records.
        """
        ...
