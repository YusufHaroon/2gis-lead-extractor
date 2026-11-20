"""Maps source names to collector classes and enforces the live-collector switch."""
from app.config import settings
from app.collectors.base import BaseCollector
from app.collectors.mock import MockCollector
from app.collectors.local_fixture import LocalFixtureCollector
from app.collectors.twogis import TwoGisCollector
from app.models.schemas import SourceInfo

_COLLECTORS: dict[str, type[BaseCollector]] = {
    MockCollector.name: MockCollector,
    LocalFixtureCollector.name: LocalFixtureCollector,
    TwoGisCollector.name: TwoGisCollector,
}


def is_enabled(name: str) -> bool:
    if name == TwoGisCollector.name:
        # Live source is available only when switched on AND an API key is configured.
        return settings.enable_live_collector and bool(settings.twogis_api_key)
    return True


def list_sources() -> list[SourceInfo]:
    """All registered sources with their enabled/export flags, for the dashboard's picker."""
    return [
        SourceInfo(
            name=name,
            label=cls.label,
            enabled=is_enabled(name),
            export_allowed=cls.export_allowed,
            is_default=name == settings.default_collector,
        )
        for name, cls in _COLLECTORS.items()
    ]


def get_collector(source: str | None) -> BaseCollector:
    name = source or settings.default_collector
    if name not in _COLLECTORS:
        raise ValueError(f"Unknown source: {name}")
    if not is_enabled(name):
        raise PermissionError("Live collector is disabled.")
    return _COLLECTORS[name]()
