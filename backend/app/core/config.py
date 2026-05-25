"""Application settings loaded from environment variables."""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AccountMode(str, Enum):
    """KIS account mode — real trading or mock trading."""

    REAL = "real"
    MOCK = "mock"


# KIS credentials grouped by which feature they unlock.
# `APP_KEY` + `APP_SECRET` are required for every KIS call.
# `ACCOUNT_NO` is only needed for account/trading endpoints.
_CORE_KIS_FIELDS = ("KIS_APP_KEY", "KIS_APP_SECRET")
_ACCOUNT_KIS_FIELDS = ("KIS_ACCOUNT_NO",)


class Settings(BaseSettings):
    """Stockquare backend settings.

    Secrets (`KIS_APP_KEY`, `KIS_APP_SECRET`, ...) are loaded from the
    environment. Missing values are logged as warnings at startup but do
    not crash the server — DB-only endpoints (e.g., empty watchlist) must
    remain functional even with partial KIS credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # KIS credentials
    kis_app_key: str = Field(default="")
    kis_app_secret: str = Field(default="")
    kis_account_no: str = Field(default="")
    kis_account_product_code: str = Field(default="01")
    kis_account_mode: AccountMode = Field(default=AccountMode.MOCK)
    kis_hts_id: str | None = Field(default=None)

    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./stockquare.db")

    # App
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Trading safety gates — Phase 2. `trading_real_mode_enabled` gates
    # order placement when KIS_ACCOUNT_MODE=real; flip to `false` to let
    # the backend run in real mode for read-only endpoints while blocking
    # order mutations entirely. `trading_max_order_amount` caps the KRW
    # value of any single order (quantity × price) — orders above this
    # limit are rejected before touching KIS. Both env vars are read by
    # the trading service's pre-flight check.
    trading_real_mode_enabled: bool = Field(default=True)
    trading_max_order_amount: int = Field(default=50_000)

    # CORS — comma-separated list via `CORS_ORIGINS` env var, e.g.
    # `CORS_ORIGINS=http://localhost:3000,https://stockquare.app`.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        """Accept either a JSON/Python list or a comma-separated string.

        An explicit empty string is interpreted as "deny all cross-origin"
        (empty list). The default factory applies only when the env var is
        unset entirely — this matches pydantic-settings precedence rules
        and avoids the footgun where `CORS_ORIGINS=` silently re-enables
        the development default.
        """
        if value is None:
            return ["http://localhost:3000"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple)):
            items: list[str] = []
            for item in value:
                if not isinstance(item, str):
                    raise TypeError(f"CORS_ORIGINS items must be strings, got {type(item).__name__}")
                stripped = item.strip()
                if stripped:
                    items.append(stripped)
            return items
        raise TypeError(f"Unsupported CORS_ORIGINS value: {value!r}")

    @property
    def kis_base_url(self) -> str:
        if self.kis_account_mode == AccountMode.REAL:
            return "https://openapi.koreainvestment.com:9443"
        return "https://openapivts.koreainvestment.com:29443"

    @property
    def kis_ws_url(self) -> str:
        # Use wss:// for TLS-encrypted streaming.
        if self.kis_account_mode == AccountMode.REAL:
            return "wss://ops.koreainvestment.com:21000"
        return "wss://ops.koreainvestment.com:31000"

    def missing_core_credentials(self) -> list[str]:
        """Return KIS env vars required for every KIS call that are empty."""
        return [
            name
            for name, value in (
                ("KIS_APP_KEY", self.kis_app_key),
                ("KIS_APP_SECRET", self.kis_app_secret),
            )
            if not value
        ]

    def missing_account_credentials(self) -> list[str]:
        """Return account-scope KIS env vars that are empty."""
        return [name for name, value in (("KIS_ACCOUNT_NO", self.kis_account_no),) if not value]

    def has_core_credentials(self) -> bool:
        return not self.missing_core_credentials()

    def has_account_credentials(self) -> bool:
        return not self.missing_account_credentials()


def log_credential_status(settings: Settings) -> None:
    """Emit a startup warning if any KIS credentials are missing.

    Does not raise: DB-only endpoints must remain serviceable even when the
    KIS credentials are incomplete. KIS-dependent endpoints will fail
    gracefully at request time with an error that names the missing fields.
    """
    missing = settings.missing_core_credentials() + settings.missing_account_credentials()
    if not missing:
        return
    if settings.app_env == "development":
        logger.info("KIS credentials not fully configured: %s", ", ".join(missing))
    else:
        logger.warning(
            "KIS credentials missing — KIS-dependent endpoints will fail until these are set: %s",
            ", ".join(missing),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
