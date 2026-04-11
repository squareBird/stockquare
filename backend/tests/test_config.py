"""Tests for Settings credential reporting and log_credential_status."""

from __future__ import annotations

import logging

import pytest

from app.core.config import Settings, log_credential_status


def _build_settings(**overrides: str) -> Settings:
    base = {
        "kis_app_key": "",
        "kis_app_secret": "",
        "kis_account_no": "",
        "app_env": "development",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_missing_core_credentials_reported() -> None:
    settings = _build_settings()
    assert settings.missing_core_credentials() == ["KIS_APP_KEY", "KIS_APP_SECRET"]
    assert settings.missing_account_credentials() == ["KIS_ACCOUNT_NO"]
    assert settings.has_core_credentials() is False
    assert settings.has_account_credentials() is False


def test_partial_credentials_core_only() -> None:
    settings = _build_settings(kis_app_key="k", kis_app_secret="s")
    assert settings.missing_core_credentials() == []
    assert settings.missing_account_credentials() == ["KIS_ACCOUNT_NO"]
    assert settings.has_core_credentials() is True
    assert settings.has_account_credentials() is False


def test_full_credentials() -> None:
    settings = _build_settings(kis_app_key="k", kis_app_secret="s", kis_account_no="12345678")
    assert settings.has_core_credentials() is True
    assert settings.has_account_credentials() is True


def test_production_missing_credentials_logs_warning_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Regression: prior implementation raised ConfigError and crashed the
    server on startup. The new contract logs a warning instead."""
    settings = _build_settings(kis_app_key="k", kis_app_secret="s", app_env="production")
    with caplog.at_level(logging.WARNING, logger="app.core.config"):
        log_credential_status(settings)
    assert any("KIS_ACCOUNT_NO" in record.message for record in caplog.records)
    assert all(record.levelno == logging.WARNING for record in caplog.records)


def test_development_missing_credentials_logs_info_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = _build_settings(app_env="development")
    with caplog.at_level(logging.INFO, logger="app.core.config"):
        log_credential_status(settings)
    # Development mode uses INFO, not WARNING.
    assert all(record.levelno == logging.INFO for record in caplog.records)


def test_full_credentials_emit_nothing(caplog: pytest.LogCaptureFixture) -> None:
    settings = _build_settings(kis_app_key="k", kis_app_secret="s", kis_account_no="12345678")
    with caplog.at_level(logging.INFO, logger="app.core.config"):
        log_credential_status(settings)
    assert caplog.records == []
