"""Tests for CORS middleware configuration."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.config import Settings


def _fresh_settings(**overrides: object) -> Settings:
    """Build Settings without .env / ambient env interference."""
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg, arg-type]


@pytest.mark.asyncio
async def test_cors_allows_configured_origin(app_client: AsyncClient) -> None:
    """Preflight from an allowed origin must echo the Origin header back."""
    response = await app_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allowed_methods
    assert "POST" in allowed_methods
    assert "OPTIONS" in allowed_methods


@pytest.mark.asyncio
async def test_cors_rejects_unconfigured_origin(app_client: AsyncClient) -> None:
    """Preflight from a non-allowlisted origin must fail with no allow-origin.

    Starlette's CORSMiddleware returns 400 "Disallowed CORS origin" and omits
    the `access-control-allow-origin` header entirely. Both are required to
    keep the browser from trusting the response.
    """
    response = await app_client.options(
        "/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_get_includes_origin_header(app_client: AsyncClient) -> None:
    """A simple GET from an allowed origin must receive the allow-origin header."""
    response = await app_client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ---------------------------------------------------------------------------
# Settings parsing
# ---------------------------------------------------------------------------


def test_cors_origins_default() -> None:
    settings = _fresh_settings()
    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_parses_comma_separated_string() -> None:
    settings = _fresh_settings(cors_origins="http://localhost:3000, https://stockquare.app")
    assert settings.cors_origins == ["http://localhost:3000", "https://stockquare.app"]


def test_cors_origins_parses_single_origin_string() -> None:
    settings = _fresh_settings(cors_origins="http://localhost:3000")
    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_accepts_list() -> None:
    settings = _fresh_settings(cors_origins=["http://a.test", "http://b.test"])
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_empty_string_denies_all() -> None:
    """`CORS_ORIGINS=` (empty) must deny all cross-origin, not revert to default."""
    settings = _fresh_settings(cors_origins="")
    assert settings.cors_origins == []


def test_cors_origins_rejects_non_string_items() -> None:
    with pytest.raises(TypeError, match="CORS_ORIGINS items must be strings"):
        _fresh_settings(cors_origins=["http://ok.test", 42])
