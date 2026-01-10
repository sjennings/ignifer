"""Tests for configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ignifer.config import (
    CONFIG_FILE_PATH,
    Settings,
    _load_config_file,
    get_settings,
    reset_settings,
)


class TestSettingsFromEnvironment:
    """Tests for loading settings from environment variables."""

    def test_opensky_credentials_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OpenSky credentials should be loaded from environment variables."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "test_user")
        monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "test_pass")

        settings = Settings()

        assert settings.opensky_username is not None
        assert settings.opensky_username.get_secret_value() == "test_user"
        assert settings.opensky_password is not None
        assert settings.opensky_password.get_secret_value() == "test_pass"

    def test_acled_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ACLED key should be loaded from environment variable."""
        monkeypatch.setenv("IGNIFER_ACLED_KEY", "acled_test_key")

        settings = Settings()

        assert settings.acled_key is not None
        assert settings.acled_key.get_secret_value() == "acled_test_key"

    def test_aisstream_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AISStream key should be loaded from environment variable."""
        monkeypatch.setenv("IGNIFER_AISSTREAM_KEY", "aisstream_test_key")

        settings = Settings()

        assert settings.aisstream_key is not None
        assert settings.aisstream_key.get_secret_value() == "aisstream_test_key"

    def test_default_values_when_no_env(self) -> None:
        """Settings should have None for credentials when not set."""
        # Create settings with cleared environment
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        assert settings.opensky_username is None
        assert settings.opensky_password is None
        assert settings.acled_key is None
        assert settings.aisstream_key is None


class TestSettingsFromConfigFile:
    """Tests for loading settings from TOML config file."""

    def test_load_from_config_file(self, tmp_path: Path) -> None:
        """Settings should be loaded from TOML config file."""
        config_content = """
opensky_username = "file_user"
opensky_password = "file_pass"
acled_key = "file_acled_key"
aisstream_key = "file_aisstream_key"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        config_data = _load_config_file(config_file)

        assert config_data["opensky_username"] == "file_user"
        assert config_data["opensky_password"] == "file_pass"
        assert config_data["acled_key"] == "file_acled_key"
        assert config_data["aisstream_key"] == "file_aisstream_key"

    def test_missing_config_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Missing config file should return empty dict."""
        nonexistent = tmp_path / "nonexistent.toml"

        config_data = _load_config_file(nonexistent)

        assert config_data == {}

    def test_invalid_toml_returns_empty_dict(self, tmp_path: Path) -> None:
        """Invalid TOML should return empty dict and not raise."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("this is not = valid [toml")

        config_data = _load_config_file(config_file)

        assert config_data == {}


class TestEnvironmentPrecedence:
    """Tests for environment variable precedence over config file."""

    def test_env_vars_take_precedence_over_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables should override config file values."""
        # Create config file with values
        config_content = """
opensky_username = "file_user"
opensky_password = "file_pass"
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        # Set env var for username only
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "env_user")

        # Patch the config file path
        with patch("ignifer.config.CONFIG_FILE_PATH", config_file):
            settings = Settings()

        # Username should come from env, password from file
        assert settings.opensky_username is not None
        assert settings.opensky_username.get_secret_value() == "env_user"
        assert settings.opensky_password is not None
        assert settings.opensky_password.get_secret_value() == "file_pass"


class TestCredentialHelperMethods:
    """Tests for credential helper methods."""

    def test_has_opensky_credentials_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """has_opensky_credentials returns True when both set."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "user")
        monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "pass")

        settings = Settings()

        assert settings.has_opensky_credentials() is True

    def test_has_opensky_credentials_false_missing_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """has_opensky_credentials returns False when password missing."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "user")

        settings = Settings()

        assert settings.has_opensky_credentials() is False

    def test_has_opensky_credentials_false_missing_username(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """has_opensky_credentials returns False when username missing."""
        monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "pass")

        settings = Settings()

        assert settings.has_opensky_credentials() is False

    def test_has_opensky_credentials_false_both_missing(self) -> None:
        """has_opensky_credentials returns False when both missing."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        assert settings.has_opensky_credentials() is False

    def test_has_acled_credentials_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """has_acled_credentials returns True when key is set."""
        monkeypatch.setenv("IGNIFER_ACLED_KEY", "key")

        settings = Settings()

        assert settings.has_acled_credentials() is True

    def test_has_acled_credentials_false(self) -> None:
        """has_acled_credentials returns False when key is not set."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        assert settings.has_acled_credentials() is False

    def test_has_aisstream_credentials_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """has_aisstream_credentials returns True when key is set."""
        monkeypatch.setenv("IGNIFER_AISSTREAM_KEY", "key")

        settings = Settings()

        assert settings.has_aisstream_credentials() is True

    def test_has_aisstream_credentials_false(self) -> None:
        """has_aisstream_credentials returns False when key is not set."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        assert settings.has_aisstream_credentials() is False

    def test_empty_string_credentials_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty string credentials should be treated as not configured."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "")
        monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "")
        monkeypatch.setenv("IGNIFER_ACLED_KEY", "")
        monkeypatch.setenv("IGNIFER_AISSTREAM_KEY", "")

        settings = Settings()

        assert settings.has_opensky_credentials() is False
        assert settings.has_acled_credentials() is False
        assert settings.has_aisstream_credentials() is False

    def test_empty_username_with_valid_password_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty username with valid password should be rejected."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "")
        monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "valid_pass")

        settings = Settings()

        assert settings.has_opensky_credentials() is False


class TestCredentialErrorMessages:
    """Tests for credential error messages."""

    def test_opensky_error_message(self) -> None:
        """OpenSky error message should be helpful."""
        msg = Settings.get_credential_error_message("opensky")

        assert "OpenSky requires authentication" in msg
        assert "IGNIFER_OPENSKY_USERNAME" in msg
        assert "IGNIFER_OPENSKY_PASSWORD" in msg
        assert "~/.config/ignifer/config.toml" in msg

    def test_acled_error_message(self) -> None:
        """ACLED error message should be helpful."""
        msg = Settings.get_credential_error_message("acled")

        assert "ACLED requires an API key" in msg
        assert "IGNIFER_ACLED_KEY" in msg
        assert "~/.config/ignifer/config.toml" in msg

    def test_aisstream_error_message(self) -> None:
        """AISStream error message should be helpful."""
        msg = Settings.get_credential_error_message("aisstream")

        assert "AISStream requires an API key" in msg
        assert "IGNIFER_AISSTREAM_KEY" in msg
        assert "~/.config/ignifer/config.toml" in msg

    def test_case_insensitive(self) -> None:
        """Error messages should work with any case."""
        msg_lower = Settings.get_credential_error_message("opensky")
        msg_upper = Settings.get_credential_error_message("OPENSKY")
        msg_mixed = Settings.get_credential_error_message("OpenSky")

        assert msg_lower == msg_upper == msg_mixed

    def test_unknown_source_message(self) -> None:
        """Unknown source should return informative message."""
        msg = Settings.get_credential_error_message("unknown_source")

        assert "Unknown data source" in msg
        assert "unknown_source" in msg


class TestCredentialSecrecy:
    """Tests for ensuring credentials are never exposed."""

    def test_repr_masks_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """repr should mask credential values."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "secret_user")
        monkeypatch.setenv("IGNIFER_OPENSKY_PASSWORD", "secret_pass")
        monkeypatch.setenv("IGNIFER_ACLED_KEY", "secret_acled")
        monkeypatch.setenv("IGNIFER_AISSTREAM_KEY", "secret_ais")

        settings = Settings()
        repr_str = repr(settings)

        # Credentials should not appear in repr
        assert "secret_user" not in repr_str
        assert "secret_pass" not in repr_str
        assert "secret_acled" not in repr_str
        assert "secret_ais" not in repr_str
        # But masked indication should be present
        assert "SecretStr('**********')" in repr_str

    def test_str_masks_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """str should mask credential values."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "secret_user")
        monkeypatch.setenv("IGNIFER_ACLED_KEY", "secret_acled")

        settings = Settings()
        str_repr = str(settings)

        # Credentials should not appear in str
        assert "secret_user" not in str_repr
        assert "secret_acled" not in str_repr

    def test_repr_shows_none_for_unset_credentials(self) -> None:
        """repr should show None for unset credentials."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        repr_str = repr(settings)
        assert "opensky_username=None" in repr_str
        assert "opensky_password=None" in repr_str

    def test_secretstr_prevents_accidental_logging(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SecretStr should prevent accidental exposure in logs."""
        monkeypatch.setenv("IGNIFER_OPENSKY_USERNAME", "secret_user")

        settings = Settings()

        # Direct str conversion of SecretStr should be masked
        username = settings.opensky_username
        assert username is not None
        assert str(username) == "**********"

        # Only get_secret_value reveals the actual value
        assert username.get_secret_value() == "secret_user"


class TestGetSettingsSingleton:
    """Tests for get_settings singleton pattern."""

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings should return the same instance."""
        reset_settings()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reset_settings_clears_singleton(self) -> None:
        """reset_settings should clear the singleton."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        assert settings1 is not settings2


class TestConfigFilePath:
    """Tests for config file path."""

    def test_default_config_path(self) -> None:
        """Default config path should be ~/.config/ignifer/config.toml."""
        expected = Path.home() / ".config" / "ignifer" / "config.toml"
        assert CONFIG_FILE_PATH == expected


class TestTTLSettings:
    """Tests for TTL settings from config file."""

    def test_ttl_from_config_file(self, tmp_path: Path) -> None:
        """TTL settings should be loadable from config file."""
        config_content = """
ttl_gdelt = 1800
ttl_opensky = 600
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(config_content)

        config_data = _load_config_file(config_file)

        assert config_data["ttl_gdelt"] == 1800
        assert config_data["ttl_opensky"] == 600

    def test_ttl_defaults(self) -> None:
        """TTL settings should have sensible defaults."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        assert settings.ttl_gdelt == 900
        assert settings.ttl_opensky == 300
        assert settings.ttl_aisstream == 900
        assert settings.ttl_worldbank == 86400
        assert settings.ttl_acled == 43200
