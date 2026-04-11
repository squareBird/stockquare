"""Authentication endpoints backed by KIS OAuth."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_kis_client
from app.core.config import AccountMode, get_settings
from app.core.exceptions import TokenExpiredError
from app.kis.client import KISClient

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatusResponse(BaseModel):
    authenticated: bool
    account_mode: AccountMode
    expires_at: datetime


class AuthDetailResponse(BaseModel):
    authenticated: bool
    account_mode: AccountMode
    expires_at: datetime | None
    remaining_seconds: int
    credentials_complete: bool
    missing_credentials: list[str]


class RevokeResponse(BaseModel):
    revoked: bool


@router.post("/token", response_model=AuthStatusResponse)
async def issue_token(client: KISClient = Depends(get_kis_client)) -> AuthStatusResponse:
    """Issue a fresh KIS access token (force-refresh)."""
    await client.token_manager.refresh()
    state = client.token_manager.state
    if state is None:
        raise TokenExpiredError()
    return AuthStatusResponse(
        authenticated=True,
        account_mode=get_settings().kis_account_mode,
        expires_at=state.expires_at,
    )


@router.get("/status", response_model=AuthDetailResponse)
async def auth_status(client: KISClient = Depends(get_kis_client)) -> AuthDetailResponse:
    """Report token state and which KIS env vars (if any) are missing.

    Frontends can use `missing_credentials` to show specific onboarding hints
    (e.g., "Add KIS_ACCOUNT_NO to enable account summary").
    """
    settings = get_settings()
    missing = settings.missing_core_credentials() + settings.missing_account_credentials()
    state = client.token_manager.state

    if state is None:
        return AuthDetailResponse(
            authenticated=False,
            account_mode=settings.kis_account_mode,
            expires_at=None,
            remaining_seconds=0,
            credentials_complete=not missing,
            missing_credentials=missing,
        )

    remaining = max(0, int((state.expires_at - datetime.now(UTC)).total_seconds()))
    return AuthDetailResponse(
        authenticated=remaining > 0,
        account_mode=settings.kis_account_mode,
        expires_at=state.expires_at,
        remaining_seconds=remaining,
        credentials_complete=not missing,
        missing_credentials=missing,
    )


@router.post("/revoke", response_model=RevokeResponse)
async def revoke_token(client: KISClient = Depends(get_kis_client)) -> RevokeResponse:
    """Revoke the current access token."""
    await client.token_manager.revoke()
    return RevokeResponse(revoked=True)
