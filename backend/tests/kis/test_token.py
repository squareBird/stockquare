"""Tests for KIS TokenManager — issue, cache, refresh, retry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.config import Settings, get_settings
from app.core.exceptions import KISNotConfiguredError, TokenExpiredError
from app.kis.models import TokenState
from app.kis.token import TokenManager


def _build_manager(handler) -> TokenManager:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    settings = get_settings()
    return TokenManager(client, settings)


@pytest.mark.asyncio
async def test_issue_token_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "abc123",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    manager = _build_manager(handler)
    token = await manager.get_token()
    assert token == "abc123"
    assert manager.state is not None
    assert manager.state.access_token == "abc123"


@pytest.mark.asyncio
async def test_token_is_cached_until_near_expiry() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(
            200,
            json={
                "access_token": f"token-{calls['count']}",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    manager = _build_manager(handler)
    first = await manager.get_token()
    second = await manager.get_token()
    assert first == second == "token-1"
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_token_refreshes_when_near_expiry() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(
            200,
            json={
                "access_token": f"token-{calls['count']}",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    manager = _build_manager(handler)
    await manager.get_token()
    # Force near-expiry.
    manager._state = TokenState(  # noqa: SLF001
        access_token="old",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    token = await manager.get_token()
    assert token.startswith("token-")
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_token_refresh_retries_and_fails() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500, json={"error": "boom"})

    manager = _build_manager(handler)
    with pytest.raises(TokenExpiredError):
        await manager.get_token()
    # 3 retries expected.
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_missing_credentials_fails_fast_without_http() -> None:
    """Regression for the market-indices blocking bug: when core KIS creds
    are empty, the token refresh must raise immediately instead of hitting
    the network and burning a retry budget."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://test")
    # Build a bare-bones Settings with blank credentials.
    settings = Settings(kis_app_key="", kis_app_secret="")  # type: ignore[call-arg]
    manager = TokenManager(http_client, settings)

    with pytest.raises(KISNotConfiguredError) as exc_info:
        await manager.get_token()

    assert "KIS_APP_KEY" in exc_info.value.missing
    assert "KIS_APP_SECRET" in exc_info.value.missing
    # Fail-fast contract: no HTTP request should have been issued.
    assert call_count["n"] == 0


@pytest.mark.asyncio
async def test_revoke_clears_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/tokenP"):
            return httpx.Response(
                200,
                json={
                    "access_token": "xyz",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        return httpx.Response(200, json={})

    manager = _build_manager(handler)
    await manager.get_token()
    assert manager.state is not None
    await manager.revoke()
    assert manager.state is None
