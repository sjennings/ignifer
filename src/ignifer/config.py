"""Configuration and logging setup for Ignifer."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Use tomllib for Python 3.11+, tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment]


# Default config file location
CONFIG_FILE_PATH = Path.home() / ".config" / "ignifer" / "config.toml"

# Error messages for missing credentials
_CREDENTIAL_ERROR_MESSAGES: dict[str, str] = {
    "opensky": (
        "OpenSky requires authentication. "
        "Set IGNIFER_OPENSKY_USERNAME and IGNIFER_OPENSKY_PASSWORD environment variables, "
        "or configure them in ~/.config/ignifer/config.toml"
    ),
    "acled": (
        "ACLED requires an API key. "
        "Set IGNIFER_ACLED_KEY environment variable, "
        "or configure acled_key in ~/.config/ignifer/config.toml"
    ),
    "aisstream": (
        "AISStream requires an API key. "
        "Set IGNIFER_AISSTREAM_KEY environment variable, "
        "or configure aisstream_key in ~/.config/ignifer/config.toml"
    ),
}


def _load_config_file(config_path: Path | None = None) -> dict[str, Any]:
    """Load configuration from TOML file if it exists.

    Args:
        config_path: Path to config file. Defaults to ~/.config/ignifer/config.toml

    Returns:
        Dictionary of configuration values, empty dict if file doesn't exist
    """
    if tomllib is None:
        # tomli not available on Python 3.10, skip config file loading
        return {}

    path = config_path or CONFIG_FILE_PATH
    if not path.exists():
        return {}

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        # Log warning but don't fail - config file is optional
        logging.getLogger(__name__).warning(
            "Failed to load config file %s: %s", path, type(e).__name__
        )
        return {}


class Settings(BaseSettings):
    """Ignifer application settings loaded from environment variables.

    Settings are loaded in priority order:
    1. Environment variables (highest priority)
    2. .env file
    3. ~/.config/ignifer/config.toml (lowest priority)

    API credentials are stored as SecretStr to prevent accidental exposure
    in logs, repr, or error messages.
    """

    model_config = SettingsConfigDict(
        env_prefix="IGNIFER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # API Keys (Phase 2+) - NEVER log these
    # Stored as SecretStr for security
    opensky_username: SecretStr | None = None
    opensky_password: SecretStr | None = None
    aisstream_key: SecretStr | None = None
    acled_key: SecretStr | None = None

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

    @model_validator(mode="before")
    @classmethod
    def load_from_config_file(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Load values from config file for any fields not set via env vars."""
        config_data = _load_config_file()

        if not config_data:
            return values

        # Map config file keys to settings fields
        # Config file uses same keys as settings fields
        config_keys = [
            "opensky_username",
            "opensky_password",
            "aisstream_key",
            "acled_key",
            "ttl_gdelt",
            "ttl_opensky",
            "ttl_aisstream",
            "ttl_worldbank",
            "ttl_acled",
            "ttl_opensanctions",
            "ttl_wikidata",
            "log_level",
            "rigor_mode",
        ]

        for key in config_keys:
            # Only use config file value if not already set (env var takes precedence)
            if key not in values or values[key] is None:
                if key in config_data:
                    values[key] = config_data[key]

        return values

    def has_opensky_credentials(self) -> bool:
        """Check if OpenSky credentials are configured.

        Returns:
            True if both username and password are non-empty, False otherwise
        """
        return bool(self.opensky_username) and bool(self.opensky_password)

    def has_acled_credentials(self) -> bool:
        """Check if ACLED API key is configured.

        Returns:
            True if ACLED key is non-empty, False otherwise
        """
        return bool(self.acled_key)

    def has_aisstream_credentials(self) -> bool:
        """Check if AISStream API key is configured.

        Returns:
            True if AISStream key is non-empty, False otherwise
        """
        return bool(self.aisstream_key)

    @staticmethod
    def get_credential_error_message(source: str) -> str:
        """Get a helpful error message for missing credentials.

        Args:
            source: The data source name (opensky, acled, aisstream)

        Returns:
            Human-readable error message explaining how to configure credentials
        """
        source_lower = source.lower()
        if source_lower in _CREDENTIAL_ERROR_MESSAGES:
            return _CREDENTIAL_ERROR_MESSAGES[source_lower]
        return f"Unknown data source: {source}. No credential configuration available."

    def __repr__(self) -> str:
        """Safe repr that masks credential values."""
        # Get non-credential fields - access model_fields from class, not instance
        fields = []
        for name in type(self).model_fields:
            value = getattr(self, name)
            if name in ("opensky_username", "opensky_password", "aisstream_key", "acled_key"):
                # Mask credentials - show only if set or not
                if value is not None:
                    fields.append(f"{name}=SecretStr('**********')")
                else:
                    fields.append(f"{name}=None")
            else:
                fields.append(f"{name}={value!r}")
        return f"Settings({', '.join(fields)})"

    def __str__(self) -> str:
        """Safe str representation that masks credential values."""
        return self.__repr__()


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the singleton Settings instance.

    Primarily used for testing to ensure fresh settings are loaded.
    """
    global _settings
    _settings = None


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
    "reset_settings",
    "configure_logging",
    "CONFIG_FILE_PATH",
]
