"""Tests for /api/v1/auth endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_issue_token(app_client: AsyncClient) -> None:
    response = await app_client.post("/api/v1/auth/token")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["account_mode"] == "mock"
    assert body["expires_at"] is not None


@pytest.mark.asyncio
async def test_auth_status_when_no_token(app_client: AsyncClient) -> None:
    response = await app_client.get("/api/v1/auth/status")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["remaining_seconds"] == 0


@pytest.mark.asyncio
async def test_auth_status_after_issue(app_client: AsyncClient) -> None:
    await app_client.post("/api/v1/auth/token")
    response = await app_client.get("/api/v1/auth/status")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["remaining_seconds"] > 0


@pytest.mark.asyncio
async def test_revoke_token(app_client: AsyncClient) -> None:
    await app_client.post("/api/v1/auth/token")
    response = await app_client.post("/api/v1/auth/revoke")
    assert response.status_code == 200
    assert response.json() == {"revoked": True}
    status = await app_client.get("/api/v1/auth/status")
    assert status.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_auth_status_reports_credential_gaps(app_client: AsyncClient) -> None:
    """Regression for Phase 1 bug: /auth/status must surface which KIS
    env vars are missing so the frontend can show specific hints."""
    response = await app_client.get("/api/v1/auth/status")
    assert response.status_code == 200
    body = response.json()
    assert "credentials_complete" in body
    assert "missing_credentials" in body
    assert isinstance(body["missing_credentials"], list)
