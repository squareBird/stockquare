"""Tests for /api/v1/strategies endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.kis.master import StockMasterRow
from app.kis.models import DailyChartCandle, DailyChartResponse
from app.models.stocks import StockMarket
from app.services.stock_index import StockMasterIndex
from tests.conftest import FakeKISClient


def _seed_index(index: StockMasterIndex) -> None:
    index.replace(
        [StockMasterRow(symbol="005930", name_ko="삼성전자", name_en="", market=StockMarket.KOSPI)]
    )


def _chart(closes: list[float]) -> DailyChartResponse:
    """Build a KIS daily-chart response (newest-first) from oldest-first closes."""
    rows = [
        DailyChartCandle(
            stck_bsop_date=f"202601{i + 1:02d}",
            stck_oprc=str(c),
            stck_hgpr=str(c),
            stck_lwpr=str(c),
            stck_clpr=str(c),
            acml_vol="1000",
        )
        for i, c in enumerate(closes)
    ]
    return DailyChartResponse(rt_cd="0", output2=list(reversed(rows)))


def _create_payload(name: str = "삼성 GC") -> dict:
    return {
        "name": name,
        "symbol": "005930",
        "sizing": {"mode": "fixed_amount", "amount_krw": 50000},
        "rule": {"indicators": [{"kind": "ma_cross", "fast": 2, "slow": 3}]},
    }


@pytest.mark.asyncio
async def test_create_strategy(app_client: AsyncClient, stock_index: StockMasterIndex) -> None:
    _seed_index(stock_index)
    resp = await app_client.post("/api/v1/strategies", json=_create_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["symbol"] == "005930"
    assert body["name_kr"] == "삼성전자"
    assert body["strategy_type"] == "rule"
    assert body["execution_mode"] == "signal_only"
    assert body["rule"]["indicators"][0]["kind"] == "ma_cross"
    assert body["last_signal"] is None


@pytest.mark.asyncio
async def test_create_rejects_unknown_symbol(
    app_client: AsyncClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index)  # index populated but without 000660
    payload = _create_payload()
    payload["symbol"] = "000660"
    resp = await app_client.post("/api/v1/strategies", json=payload)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_SYMBOL"


@pytest.mark.asyncio
async def test_create_rejects_non_rule_type(
    app_client: AsyncClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index)
    payload = _create_payload()
    payload["strategy_type"] = "ai"
    resp = await app_client.post("/api/v1/strategies", json=payload)
    assert resp.status_code == 422  # Phase 1 supports rule only


@pytest.mark.asyncio
async def test_create_rejects_bad_indicator(
    app_client: AsyncClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index)
    payload = _create_payload()
    payload["rule"] = {"indicators": [{"kind": "ma_cross", "fast": 5}]}  # missing slow
    resp = await app_client.post("/api/v1/strategies", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_and_get_strategy(
    app_client: AsyncClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index)
    created = (await app_client.post("/api/v1/strategies", json=_create_payload())).json()

    listing = await app_client.get("/api/v1/strategies")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] == 1
    assert body["strategies"][0]["id"] == created["id"]

    one = await app_client.get(f"/api/v1/strategies/{created['id']}")
    assert one.status_code == 200
    assert one.json()["name"] == "삼성 GC"


@pytest.mark.asyncio
async def test_get_missing_strategy_404(app_client: AsyncClient) -> None:
    resp = await app_client.get("/api/v1/strategies/9999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "STRATEGY_NOT_FOUND"


@pytest.mark.asyncio
async def test_evaluate_produces_and_persists_signal(
    app_client: AsyncClient, fake_kis_client: FakeKISClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index)
    created = (await app_client.post("/api/v1/strategies", json=_create_payload())).json()

    # Golden-cross series -> the ma_cross(2/3) rule signals buy.
    fake_kis_client.inquire_daily_itemchartprice.return_value = _chart([10, 10, 10, 8, 14])
    evaluate = await app_client.post(f"/api/v1/strategies/{created['id']}/evaluate")
    assert evaluate.status_code == 200, evaluate.text
    signal = evaluate.json()
    assert signal["action"] == "buy"
    assert signal["executed"] is False  # Phase 1 never executes

    # The signal is persisted and surfaces in history + as last_signal.
    history = await app_client.get(f"/api/v1/strategies/{created['id']}/signals")
    assert history.status_code == 200
    assert history.json()["count"] == 1

    listing = await app_client.get("/api/v1/strategies")
    assert listing.json()["strategies"][0]["last_signal"]["action"] == "buy"


@pytest.mark.asyncio
async def test_update_strategy(app_client: AsyncClient, stock_index: StockMasterIndex) -> None:
    _seed_index(stock_index)
    created = (await app_client.post("/api/v1/strategies", json=_create_payload())).json()
    resp = await app_client.patch(
        f"/api/v1/strategies/{created['id']}", json={"name": "이름 변경"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "이름 변경"


@pytest.mark.asyncio
async def test_delete_strategy(app_client: AsyncClient, stock_index: StockMasterIndex) -> None:
    _seed_index(stock_index)
    created = (await app_client.post("/api/v1/strategies", json=_create_payload())).json()
    delete = await app_client.delete(f"/api/v1/strategies/{created['id']}")
    assert delete.status_code == 204
    after = await app_client.get(f"/api/v1/strategies/{created['id']}")
    assert after.status_code == 404
