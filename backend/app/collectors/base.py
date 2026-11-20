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


class BaseCollector(ABC):
    name: str = "base"
    export_allowed: bool = False  # whether the source licence permits Excel export

    @abstractmethod
    def collect(self, category: str, location: str, max_results: int) -> AsyncIterator[RawListing]:
        """Yield raw listings, respecting max_results and source limits."""
        ...
