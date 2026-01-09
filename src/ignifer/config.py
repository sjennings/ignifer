"""Configuration and logging setup for Ignifer."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ignifer application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="IGNIFER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API Keys (Phase 2+) - NEVER log these
    opensky_username: str | None = None
    opensky_password: str | None = None
    aisstream_key: str | None = None
    acled_key: str | None = None

    # Cache TTL defaults (seconds)
    ttl_gdelt: int = 900  # 15 minutes (news is time-sensitive)
    ttl_opensky: int = 300  # 5 minutes
    ttl_aisstream: int = 900  # 15 minutes
    ttl_worldbank: int = 86400  # 24 hours
    ttl_acled: int = 43200  # 12 hours
    ttl_opensanctions: int = 86400  # 24 hours
    ttl_wikidata: int = 604800  # 7 days

    # Logging
    log_level: str = "INFO"

    # Rigor mode (Phase 4)
    rigor_mode: bool = False


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def configure_logging(level: str = "INFO") -> None:
    """Configure stdlib logging for Ignifer."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Suppress httpx debug logs (too verbose)
    logging.getLogger("httpx").setLevel(logging.WARNING)


__all__ = [
    "Settings",
    "get_settings",
    "configure_logging",
]
