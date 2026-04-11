"""KIS OAuth token manager with in-memory caching and auto-refresh."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import Settings
from app.core.exceptions import KISAPIError, KISNotConfiguredError, TokenExpiredError
from app.kis.models import TokenResponse, TokenState

logger = logging.getLogger(__name__)

_REFRESH_BUFFER = timedelta(minutes=5)
_MAX_RETRIES = 3
_BASE_DELAY = 1.0


class TokenManager:
    """Issues and caches KIS OAuth access tokens in memory."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._state: TokenState | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> TokenState | None:
        return self._state

    async def get_token(self) -> str:
        """Return a valid access token, refreshing if needed.

        Uses double-checked locking so cached tokens return without
        acquiring the lock, and a slow refresh does not block the hot path.
        """
        if not self._is_expired():
            state = self._state
            if state is not None:
                return state.access_token

        async with self._lock:
            if self._is_expired():
                await self._refresh_locked()
            state = self._state
            if state is None:
                raise TokenExpiredError()
            return state.access_token

    async def refresh(self) -> None:
        """Force a token refresh."""
        async with self._lock:
            await self._refresh_locked()

    async def revoke(self) -> None:
        """Revoke the current token via KIS /oauth2/revokeP."""
        async with self._lock:
            if self._state is None:
                return
            try:
                await self._client.post(
                    f"{self._settings.kis_base_url}/oauth2/revokeP",
                    json={
                        "appkey": self._settings.kis_app_key,
                        "appsecret": self._settings.kis_app_secret,
                        "token": self._state.access_token,
                    },
                )
            except httpx.HTTPError as exc:
                # Do not surface the exception message: it may echo auth
                # headers or query strings. Log only the exception type.
                logger.warning("Token revoke request failed: %s", type(exc).__name__)
            finally:
                self._state = None

    def _is_expired(self) -> bool:
        if self._state is None:
            return True
        return datetime.now(UTC) >= self._state.expires_at - _REFRESH_BUFFER

    async def _refresh_locked(self) -> None:
        last_error_type: str | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                self._state = await self._issue_token()
                logger.info(
                    "KIS token issued",
                    extra={"expires_at": self._state.expires_at.isoformat()},
                )
                return
            except KISNotConfiguredError:
                # Not a transient error — do not retry.
                raise
            except KISAPIError as exc:
                last_error_type = type(exc).__name__
                if attempt == _MAX_RETRIES - 1:
                    break
                await asyncio.sleep(_BASE_DELAY * (2**attempt))
        logger.error("KIS token refresh failed after retries: %s", last_error_type)
        raise TokenExpiredError()

    async def _issue_token(self) -> TokenState:
        # Fail-fast if core credentials are missing, so the retry loop does
        # not burn ~30s + KIS timeouts on a clearly unconfigured deployment.
        missing = self._settings.missing_core_credentials()
        if missing:
            raise KISNotConfiguredError(missing)

        url = f"{self._settings.kis_base_url}/oauth2/tokenP"
        payload = {
            "grant_type": "client_credentials",
            "appkey": self._settings.kis_app_key,
            "appsecret": self._settings.kis_app_secret,
        }
        try:
            response = await self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Token request network error: %s", type(exc).__name__)
            raise KISAPIError() from exc

        if response.status_code >= 400:
            logger.warning("Token request rejected", extra={"status": response.status_code})
            raise KISAPIError()

        data = TokenResponse.model_validate(response.json())
        expires_at = datetime.now(UTC) + timedelta(seconds=data.expires_in)
        return TokenState(access_token=data.access_token, expires_at=expires_at)
