"""Maps source names to collector classes and enforces the live-collector switch."""
from app.config import settings
from app.collectors.base import BaseCollector
from app.collectors.mock import MockCollector
from app.collectors.local_fixture import LocalFixtureCollector
from app.collectors.twogis import TwoGisCollector

_COLLECTORS: dict[str, type[BaseCollector]] = {
    MockCollector.name: MockCollector,
    LocalFixtureCollector.name: LocalFixtureCollector,
    TwoGisCollector.name: TwoGisCollector,
}


def get_collector(source: str | None) -> BaseCollector:
    name = source or settings.default_collector
    if name not in _COLLECTORS:
        raise ValueError(f"Unknown source: {name}")
    if name == TwoGisCollector.name and not settings.enable_live_collector:
        raise PermissionError("Live collector is disabled.")
    return _COLLECTORS[name]()
