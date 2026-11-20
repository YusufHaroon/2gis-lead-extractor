"""Application settings loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    default_collector: str = "mock"
    enable_live_collector: bool = False
    max_results_cap: int = 200
    collector_timeout_seconds: int = 120
    max_concurrent_jobs: int = 3
    cors_origins: str = "http://localhost:3000"

    # Live 2GIS Catalog API collector (used only when source=twogis and the key is set).
    # Keep the key server-side; it is never sent to the browser.
    twogis_api_key: str = ""
    twogis_api_base: str = "https://catalog.api.2gis.com"
    twogis_region_id: str = ""  # optional: pin a region id; otherwise resolved from the location

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
