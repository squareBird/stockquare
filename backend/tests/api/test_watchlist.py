"""Tests for /api/v1/watchlist endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import InvalidSymbolError, KISAPIError
from app.kis.master import StockMasterRow
from app.kis.models import StockPriceOutput, StockPriceResponse
from app.models.stocks import StockMarket
from app.services.stock_index import StockMasterIndex
from tests.conftest import FakeKISClient


def _price_response(
    symbol: str = "005930",
    name: str = "삼성전자",
    price: str = "72000",
) -> StockPriceResponse:
    return StockPriceResponse(
        rt_cd="0",
        output=StockPriceOutput(
            stck_shrn_iscd=symbol,
            hts_kor_isnm=name,
            stck_prpr=price,
            prdy_vrss="1500",
            prdy_ctrt="2.13",
            acml_vol="15000000",
        ),
    )


def _seed_index(index: StockMasterIndex, *rows: tuple[str, str]) -> None:
    """Seed the master index with (symbol, korean name) pairs so name
    resolution has a source — inquire-price carries no stock name."""
    index.replace(
        [
            StockMasterRow(symbol=symbol, name_ko=name, name_en="", market=StockMarket.KOSPI)
            for symbol, name in rows
        ]
    )


@pytest.mark.asyncio
async def test_watchlist_add_list_delete_flow(
    app_client: AsyncClient, fake_kis_client: FakeKISClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index, ("005930", "삼성전자"))
    fake_kis_client.inquire_stock_price.return_value = _price_response()

    # Add
    add = await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})
    assert add.status_code == 201
    item = add.json()
    assert item["symbol"] == "005930"
    assert item["name"] == "삼성전자"
    item_id = item["id"]

    # List (with enriched price + live Korean name)
    listing = await app_client.get("/api/v1/watchlist")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] == 1
    assert body["errors"] == []
    assert body["items"][0]["name"] == "삼성전자"
    assert body["items"][0]["price"] == 72000
    assert body["items"][0]["change_rate"] == pytest.approx(2.13)

    # Delete
    delete = await app_client.delete(f"/api/v1/watchlist/{item_id}")
    assert delete.status_code == 204

    after = await app_client.get("/api/v1/watchlist")
    assert after.json()["count"] == 0


@pytest.mark.asyncio
async def test_watchlist_list_uses_korean_name_from_index(
    app_client: AsyncClient, fake_kis_client: FakeKISClient, stock_index: StockMasterIndex
) -> None:
    """GET /watchlist must surface the master-index Korean name instead of
    echoing the stored symbol. inquire-price (FHKST01010100) carries no stock
    name, so the name is resolved from the in-memory master index at read time —
    an index refresh (renamed/relisted symbol) surfaces without a DB migration."""
    _seed_index(stock_index, ("005930", "삼성전자"))
    fake_kis_client.inquire_stock_price.return_value = _price_response()
    await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})

    # A later index refresh renames the listing; the new name surfaces on read.
    _seed_index(stock_index, ("005930", "삼성전자우"))
    listing = await app_client.get("/api/v1/watchlist")
    assert listing.status_code == 200
    body = listing.json()
    assert body["items"][0]["name"] == "삼성전자우"


@pytest.mark.asyncio
async def test_watchlist_name_falls_back_to_symbol_when_index_empty(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """When the master index has no row for a symbol (e.g. a freshly listed
    code not yet in the snapshot), the name falls back to the symbol rather
    than failing — the row still renders, just without a friendly name."""
    fake_kis_client.inquire_stock_price.return_value = _price_response()
    await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})
    listing = await app_client.get("/api/v1/watchlist")
    body = listing.json()
    assert body["items"][0]["name"] == "005930"


@pytest.mark.asyncio
async def test_watchlist_duplicate(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_stock_price.return_value = _price_response()
    await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})
    dup = await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})
    assert dup.status_code == 409
    assert dup.json()["code"] == "DUPLICATE_SYMBOL"


@pytest.mark.asyncio
async def test_watchlist_invalid_symbol_format(app_client: AsyncClient) -> None:
    resp = await app_client.post("/api/v1/watchlist", json={"symbol": "ABC"})
    assert resp.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_watchlist_kis_rejects_symbol(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_stock_price.side_effect = InvalidSymbolError("999999")
    resp = await app_client.post("/api/v1/watchlist", json={"symbol": "999999"})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_SYMBOL"


@pytest.mark.asyncio
async def test_watchlist_delete_not_found(app_client: AsyncClient) -> None:
    resp = await app_client.delete("/api/v1/watchlist/9999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_watchlist_reorder(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_stock_price.return_value = _price_response()
    first = await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})

    fake_kis_client.inquire_stock_price.return_value = _price_response(symbol="000660", name="SK하이닉스")
    second = await app_client.post("/api/v1/watchlist", json={"symbol": "000660"})

    reorder = await app_client.patch(
        "/api/v1/watchlist/reorder",
        json={
            "order": [
                {"id": second.json()["id"], "sort_order": 0},
                {"id": first.json()["id"], "sort_order": 1},
            ],
        },
    )
    assert reorder.status_code == 200
    assert reorder.json()["updated"] == 2


@pytest.mark.asyncio
async def test_empty_watchlist_returns_200_without_kis_calls(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """Regression: empty watchlist on fresh deploy must return 200 with
    empty `items` / `errors` / `count` and never invoke KIS."""
    resp = await app_client.get("/api/v1/watchlist")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "errors": [], "count": 0}
    fake_kis_client.inquire_stock_price.assert_not_called()


@pytest.mark.asyncio
async def test_watchlist_partial_failure_moves_failed_to_errors(
    app_client: AsyncClient, fake_kis_client: FakeKISClient, stock_index: StockMasterIndex
) -> None:
    """Regression for Phase 1.5: one symbol fails → it moves to `errors[]`,
    the healthy siblings stay in `items[]`, and HTTP status stays 200.
    The legacy `price:0` silent-degrade behavior is gone."""
    _seed_index(stock_index, ("005930", "삼성전자"), ("000660", "SK하이닉스"))
    # Seed two items while KIS is healthy.
    fake_kis_client.inquire_stock_price.return_value = _price_response(name="삼성전자")
    await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})

    fake_kis_client.inquire_stock_price.return_value = _price_response(symbol="000660", name="SK하이닉스")
    await app_client.post("/api/v1/watchlist", json={"symbol": "000660"})

    # Now the list-time enrichment: first call succeeds, second fails.
    fake_kis_client.inquire_stock_price.side_effect = [
        _price_response(symbol="005930", name="삼성전자"),
        KISAPIError(),
    ]
    listing = await app_client.get("/api/v1/watchlist")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] == 2
    assert len(body["items"]) == 1
    assert body["items"][0]["symbol"] == "005930"
    assert body["items"][0]["name"] == "삼성전자"
    assert body["items"][0]["price"] == 72000
    assert len(body["errors"]) == 1
    assert body["errors"][0]["symbol"] == "000660"
    assert body["errors"][0]["error_code"] == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_watchlist_all_enrichments_fail_still_returns_200(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """A DB query success with 100% KIS failure must still return 200 —
    the watchlist DB itself is the source of truth for what exists."""
    fake_kis_client.inquire_stock_price.return_value = _price_response()
    await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})

    fake_kis_client.inquire_stock_price.side_effect = KISAPIError()
    listing = await app_client.get("/api/v1/watchlist")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] == 1
    assert body["items"] == []
    assert len(body["errors"]) == 1
    assert body["errors"][0]["symbol"] == "005930"


@pytest.mark.asyncio
async def test_watchlist_reorder_missing_id(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_stock_price.return_value = _price_response()
    created = await app_client.post("/api/v1/watchlist", json={"symbol": "005930"})
    existing_id = created.json()["id"]

    resp = await app_client.patch(
        "/api/v1/watchlist/reorder",
        json={
            "order": [
                {"id": existing_id, "sort_order": 0},
                {"id": 99999, "sort_order": 1},
            ],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_watchlist_full(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    # Fill the watchlist up to the limit (20).
    for i in range(20):
        fake_kis_client.inquire_stock_price.return_value = _price_response(name=f"Stock {i}")
        symbol = f"00{i:04d}"
        resp = await app_client.post("/api/v1/watchlist", json={"symbol": symbol})
        assert resp.status_code == 201, resp.text

    # The 21st add must be rejected.
    fake_kis_client.inquire_stock_price.return_value = _price_response(name="Overflow")
    overflow = await app_client.post("/api/v1/watchlist", json={"symbol": "999999"})
    assert overflow.status_code == 400
    assert overflow.json()["code"] == "WATCHLIST_FULL"
