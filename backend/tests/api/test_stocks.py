"""Tests for /api/v1/stocks endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import InvalidSymbolError
from app.kis.master import StockMasterRow
from app.kis.models import (
    DailyChartCandle,
    DailyChartResponse,
    SearchInfoOutput,
    SearchInfoResponse,
    StockPriceOutput,
    StockPriceResponse,
)
from app.models.stocks import StockMarket
from app.services.stock_index import StockMasterIndex
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
    fake_kis_client.search_info.return_value = SearchInfoResponse(
        rt_cd="0",
        output=SearchInfoOutput(
            shtn_pdno="005930",
            prdt_name="Samsung Electronics",
            mket_id_cd="STK",
        ),
    )
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "005930"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["symbol"] == "005930"
    # inquire-price carries no stock name; the name comes from search-info's
    # prdt_name (the authoritative product name).
    assert body["items"][0]["name"] == "Samsung Electronics"


@pytest.mark.asyncio
async def test_stock_search_by_korean_name(
    app_client: AsyncClient,
    stock_index: StockMasterIndex,
) -> None:
    stock_index.replace(
        [
            StockMasterRow(
                symbol="005930",
                name_ko="삼성전자",
                name_en="",
                market=StockMarket.KOSPI,
            ),
        ]
    )
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "삼성전자"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["items"][0]["symbol"] == "005930"
    assert body["items"][0]["name"] == "삼성전자"
    assert body["items"][0]["market"] == "KOSPI"


@pytest.mark.asyncio
async def test_stock_search_by_us_ticker(
    app_client: AsyncClient,
    stock_index: StockMasterIndex,
) -> None:
    stock_index.replace(
        [
            StockMasterRow(
                symbol="AMZN",
                name_ko="",
                name_en="AMAZON.COM INC",
                market=StockMarket.NASDAQ,
            ),
        ]
    )

    resp_ticker = await app_client.get("/api/v1/stocks/search", params={"q": "AMZN"})
    assert resp_ticker.status_code == 200
    body_ticker = resp_ticker.json()
    assert body_ticker["count"] == 1
    assert body_ticker["items"][0]["symbol"] == "AMZN"
    assert body_ticker["items"][0]["market"] == "NASDAQ"

    resp_name = await app_client.get("/api/v1/stocks/search", params={"q": "amazon"})
    assert resp_name.status_code == 200
    body_name = resp_name.json()
    assert body_name["count"] == 1
    assert body_name["items"][0]["symbol"] == "AMZN"
    assert body_name["items"][0]["name"] == "AMAZON.COM INC"


@pytest.mark.asyncio
async def test_stock_search_multi_hit_respects_limit(
    app_client: AsyncClient,
    stock_index: StockMasterIndex,
) -> None:
    stock_index.replace(
        [
            StockMasterRow(symbol="005930", name_ko="삼성전자", name_en="", market=StockMarket.KOSPI),
            StockMasterRow(symbol="006400", name_ko="삼성SDI", name_en="", market=StockMarket.KOSPI),
            StockMasterRow(symbol="028260", name_ko="삼성물산", name_en="", market=StockMarket.KOSPI),
            StockMasterRow(symbol="207940", name_ko="삼성바이오로직스", name_en="", market=StockMarket.KOSPI),
            StockMasterRow(symbol="032830", name_ko="삼성생명", name_en="", market=StockMarket.KOSPI),
        ]
    )
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "삼성", "limit": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    returned_symbols = [item["symbol"] for item in body["items"]]
    assert len(returned_symbols) == 3
    assert len(set(returned_symbols)) == 3


@pytest.mark.asyncio
async def test_stock_search_empty_index_text_query_returns_empty(
    app_client: AsyncClient,
) -> None:
    resp = await app_client.get("/api/v1/stocks/search", params={"q": "Samsung"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["items"] == []


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


def _chart_response() -> DailyChartResponse:
    """Two daily candles (KIS newest-first) plus a blank padding row."""
    return DailyChartResponse(
        rt_cd="0",
        output2=[
            DailyChartCandle(
                stck_bsop_date="20260502",
                stck_oprc="71000",
                stck_hgpr="72500",
                stck_lwpr="70800",
                stck_clpr="72000",
                acml_vol="12345678",
            ),
            DailyChartCandle(
                stck_bsop_date="20260501",
                stck_oprc="70000",
                stck_hgpr="71000",
                stck_lwpr="69500",
                stck_clpr="70800",
                acml_vol="9876543",
            ),
            DailyChartCandle(stck_bsop_date=""),
        ],
    )


@pytest.mark.asyncio
async def test_stock_history_success(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_itemchartprice.return_value = _chart_response()
    resp = await app_client.get("/api/v1/stocks/005930/history", params={"period": "1m"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "005930"
    assert body["period"] == "1m"
    # KIS rows are newest-first; the service reverses them to oldest-first and
    # drops the blank padding row.
    assert [c["time"] for c in body["candles"]] == ["2026-05-01", "2026-05-02"]
    assert body["candles"][0]["open"] == 70000
    assert body["candles"][1]["close"] == 72000
    assert body["candles"][1]["volume"] == 12345678


@pytest.mark.asyncio
async def test_stock_history_defaults_to_one_month(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_itemchartprice.return_value = _chart_response()
    resp = await app_client.get("/api/v1/stocks/005930/history")
    assert resp.status_code == 200
    assert resp.json()["period"] == "1m"


@pytest.mark.asyncio
async def test_stock_history_symbol_not_found(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_itemchartprice.side_effect = InvalidSymbolError("999999")
    resp = await app_client.get("/api/v1/stocks/999999/history")
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_SYMBOL"


@pytest.mark.asyncio
async def test_stock_history_invalid_period(app_client: AsyncClient) -> None:
    resp = await app_client.get("/api/v1/stocks/005930/history", params={"period": "5y"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_stock_history_bad_symbol_format(app_client: AsyncClient) -> None:
    resp = await app_client.get("/api/v1/stocks/ABC/history")
    assert resp.status_code == 422
