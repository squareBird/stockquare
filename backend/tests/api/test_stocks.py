"""Tests for /api/v1/stocks endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import InvalidSymbolError, KISAPIError
from app.kis.models import (
    SearchInfoOutput,
    SearchInfoResponse,
    StockPriceOutput,
    StockPriceResponse,
)
from tests.conftest import FakeKISClient


def _price_response(name: str = "Samsung", price: str = "72000") -> StockPriceResponse:
    return StockPriceResponse(
        rt_cd="0",
        output=StockPriceOutput(
            stck_shrn_iscd="005930",
            hts_kor_isnm=name,
            stck_prpr=price,
            prdy_vrss="1500",
            prdy_ctrt="2.13",
            acml_vol="15000000",
        ),
    )


@pytest.mark.asyncio
async def test_stock_search_by_symbol(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_stock_price.return_value = _price_response(name="Samsung")
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "005930"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["symbol"] == "005930"
    assert body["items"][0]["name"] == "Samsung"


@pytest.mark.asyncio
async def test_stock_search_by_name(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.search_info.return_value = SearchInfoResponse(
        rt_cd="0",
        output=SearchInfoOutput(
            shtn_pdno="005930",
            prdt_name="Samsung Electronics",
            mket_id_cd="STK",
        ),
    )
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "Samsung"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["symbol"] == "005930"
    assert body["items"][0]["market"] == "KOSPI"


@pytest.mark.asyncio
async def test_stock_search_empty_query(app_client: AsyncClient) -> None:
    resp = await app_client.get("/api/v1/stocks/search", params={"q": ""})
    assert resp.status_code == 422  # min_length=1 rejected by FastAPI


@pytest.mark.asyncio
async def test_stock_search_symbol_not_found(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_stock_price.side_effect = InvalidSymbolError("999999")
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "999999"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_stock_search_kis_failure_returns_empty(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.search_info.side_effect = KISAPIError()
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "Samsung"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
