"""Tests for /api/v1/market endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import KISAPIError
from app.kis.models import IndexOutput, IndexResponse
from tests.conftest import FakeKISClient


def _index_response(value: str = "2650.32") -> IndexResponse:
    return IndexResponse(
        rt_cd="0",
        output=IndexOutput(
            bstp_nmix_prpr=value,
            bstp_nmix_prdy_vrss="15.2",
            bstp_nmix_prdy_ctrt="0.58",
            acml_vol="450000000",
        ),
    )


@pytest.mark.asyncio
async def test_market_indices_full_success(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_index.side_effect = [
        _index_response("2650.32"),
        _index_response("870.15"),
    ]
    response = await app_client.get("/api/v1/market/indices")
    assert response.status_code == 200
    body = response.json()
    assert len(body["indices"]) == 2
    assert body["errors"] == []
    assert body["indices"][0]["name"] == "KOSPI"
    assert body["indices"][0]["value"] == pytest.approx(2650.32)
    assert body["indices"][1]["name"] == "KOSDAQ"


@pytest.mark.asyncio
async def test_market_indices_partial_failure_returns_200(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """KIS occasionally 500s on one index code while the other succeeds.
    The endpoint must degrade gracefully instead of returning 502."""
    fake_kis_client.inquire_index.side_effect = [
        _index_response("2650.32"),
        KISAPIError(),
    ]
    response = await app_client.get("/api/v1/market/indices")
    assert response.status_code == 200
    body = response.json()
    assert len(body["indices"]) == 1
    assert body["indices"][0]["name"] == "KOSPI"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == "1001"
    assert body["errors"][0]["name"] == "KOSDAQ"
    assert body["errors"][0]["error_code"] == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_market_indices_first_failure_second_success(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """KOSPI fails, KOSDAQ succeeds — the healthy index must still surface."""
    fake_kis_client.inquire_index.side_effect = [
        KISAPIError(),
        _index_response("870.15"),
    ]
    response = await app_client.get("/api/v1/market/indices")
    assert response.status_code == 200
    body = response.json()
    assert len(body["indices"]) == 1
    assert body["indices"][0]["name"] == "KOSDAQ"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["name"] == "KOSPI"


@pytest.mark.asyncio
async def test_market_indices_full_failure_returns_502(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    """Only when every index fails should the endpoint return 502."""
    fake_kis_client.inquire_index.side_effect = KISAPIError()
    resp = await app_client.get("/api/v1/market/indices")
    assert resp.status_code == 502
    assert resp.json()["code"] == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_market_indices_all_missing_credentials_returns_503(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """When the full failure is caused by unset KIS credentials, preserve
    the 503 KIS_NOT_CONFIGURED semantic instead of collapsing to 502."""
    from app.core.exceptions import KISNotConfiguredError

    fake_kis_client.inquire_index.side_effect = KISNotConfiguredError(["KIS_APP_KEY", "KIS_APP_SECRET"])
    resp = await app_client.get("/api/v1/market/indices")
    assert resp.status_code == 503
    assert resp.json()["code"] == "KIS_NOT_CONFIGURED"
