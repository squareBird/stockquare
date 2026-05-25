"""Tests for /api/v1/orders (Phase 2 trading)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db_session, get_kis_client
from app.core.config import AccountMode, Settings, get_settings
from app.kis.models import (
    DailyCcldOutput,
    DailyCcldResponse,
    OrderCashOutput,
    OrderCashResponse,
)
from app.main import create_app
from tests.conftest import FakeKISClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _order_ok(
    branch: str = "01234",
    odno: str = "0000012345",
    ord_tmd: str = "093014",
) -> OrderCashResponse:
    return OrderCashResponse(
        rt_cd="0",
        msg_cd="OPSP0000",
        msg1="주문이 정상적으로 접수되었습니다",
        output=OrderCashOutput(
            KRX_FWDG_ORD_ORGNO=branch,
            ODNO=odno,
            ORD_TMD=ord_tmd,
        ),
    )


def _order_rejected(
    message: str = "주문 가격이 상하한가를 벗어났습니다",
    msg_cd: str = "APBK0918",
) -> OrderCashResponse:
    return OrderCashResponse(
        rt_cd="1",
        msg_cd=msg_cd,
        msg1=message,
        output=None,
    )


def _daily_ccld(rows: list[DailyCcldOutput]) -> DailyCcldResponse:
    return DailyCcldResponse(rt_cd="0", output1=rows)


def _exec_row(
    *,
    odno: str = "0000012345",
    symbol: str = "005930",
    name: str = "삼성전자",
    side: str = "02",  # buy
    order_type: str = "00",  # limit
    quantity: str = "1",
    filled: str = "0",
    price: str = "72000",
    cancelled: str = "N",
    ord_tmd: str = "093014",
) -> DailyCcldOutput:
    return DailyCcldOutput(
        odno=odno,
        orgn_odno="",
        ord_gno_brno="01234",
        pdno=symbol,
        prdt_name=name,
        sll_buy_dvsn_cd=side,
        ord_dvsn_cd=order_type,
        ord_qty=quantity,
        tot_ccld_qty=filled,
        ord_unpr=price,
        avg_prvs="0",
        ord_tmd=ord_tmd,
        cncl_yn=cancelled,
    )


# ---------------------------------------------------------------------------
# Settings override fixture (for real-mode / cap tests)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_mode_client(
    fake_kis_client: FakeKISClient,
    db_session,
) -> AsyncIterator[tuple[AsyncClient, Settings]]:
    """Spin up an app-client bound to a real-mode Settings override.

    Used for safety-gate tests that need to flip KIS_ACCOUNT_MODE or
    TRADING_REAL_MODE_ENABLED without mutating the process environment.
    """
    app = create_app()
    test_settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        kis_app_key="test-app-key",
        kis_app_secret="test-app-secret",
        kis_account_no="12345678",
        kis_account_product_code="01",
        kis_account_mode=AccountMode.REAL,
        trading_real_mode_enabled=False,  # blocks order mutations
        trading_max_order_amount=50_000,
    )

    async def _override_session():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_kis_client] = lambda: fake_kis_client
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, test_settings
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def low_cap_client(
    fake_kis_client: FakeKISClient,
    db_session,
) -> AsyncIterator[AsyncClient]:
    """Mock-mode client with a 5_000 KRW order cap — used to exercise the
    amount-cap gate without leaving mock mode."""
    app = create_app()
    test_settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        kis_app_key="test-app-key",
        kis_app_secret="test-app-secret",
        kis_account_no="12345678",
        kis_account_product_code="01",
        kis_account_mode=AccountMode.MOCK,
        trading_real_mode_enabled=True,
        trading_max_order_amount=5_000,
    )

    async def _override_session():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_kis_client] = lambda: fake_kis_client
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_buy_order_happy_path(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.order_cash.return_value = _order_ok()
    resp = await app_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "limit",
            "quantity": 1,
            "price": 5000,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["order_id"] == "01234-0000012345"
    assert body["side"] == "buy"
    assert body["order_type"] == "limit"
    assert body["status"] == "submitted"
    assert body["quantity"] == 1
    assert body["price"] == 5000

    # KIS was called with the mapped tr_id path
    call_kwargs = fake_kis_client.order_cash.call_args.kwargs
    assert call_kwargs["symbol"] == "005930"
    assert call_kwargs["side"] == "buy"
    assert call_kwargs["order_type"] == "limit"
    assert call_kwargs["quantity"] == 1
    assert call_kwargs["price"] == 5000


@pytest.mark.asyncio
async def test_create_sell_order(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.order_cash.return_value = _order_ok(odno="0000099999")
    resp = await app_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "sell",
            "order_type": "limit",
            "quantity": 1,
            "price": 5000,
        },
    )
    assert resp.status_code == 201
    assert fake_kis_client.order_cash.call_args.kwargs["side"] == "sell"


@pytest.mark.asyncio
async def test_create_market_order_within_last_price_cap(
    low_cap_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """Regression for Phase 2 security review CRITICAL:
    market orders now fetch the last-traded price and enforce the cap
    against `quantity × last_price`. A 1-share order at 4,500 KRW must
    pass the 5,000 KRW cap."""
    from app.kis.models import StockPriceOutput, StockPriceResponse

    fake_kis_client.inquire_stock_price.return_value = StockPriceResponse(
        rt_cd="0",
        output=StockPriceOutput(
            stck_shrn_iscd="005930",
            hts_kor_isnm="삼성전자",
            stck_prpr="4500",
            prdy_vrss="0",
            prdy_ctrt="0",
            acml_vol="0",
        ),
    )
    fake_kis_client.order_cash.return_value = _order_ok()
    resp = await low_cap_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "market",
            "quantity": 1,
            "price": None,
        },
    )
    assert resp.status_code == 201
    # inquire_stock_price was consulted for the cap check.
    fake_kis_client.inquire_stock_price.assert_called_once()


@pytest.mark.asyncio
async def test_create_market_order_rejected_by_last_price_cap(
    low_cap_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """Market order whose notional exceeds the 5,000 KRW cap must be
    rejected BEFORE the order_cash call. Closes the Phase 2 CRITICAL
    bypass where market orders skipped the cap entirely."""
    from app.kis.models import StockPriceOutput, StockPriceResponse

    fake_kis_client.inquire_stock_price.return_value = StockPriceResponse(
        rt_cd="0",
        output=StockPriceOutput(
            stck_shrn_iscd="005930",
            hts_kor_isnm="삼성전자",
            stck_prpr="72000",  # ~72k KRW per share → 1 share > 5k cap
            prdy_vrss="0",
            prdy_ctrt="0",
            acml_vol="0",
        ),
    )
    resp = await low_cap_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "market",
            "quantity": 1,
            "price": None,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "ORDER_AMOUNT_EXCEEDED"
    fake_kis_client.order_cash.assert_not_called()


@pytest.mark.asyncio
async def test_create_limit_order_without_price_rejected(
    app_client: AsyncClient,
) -> None:
    resp = await app_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "limit",
            "quantity": 1,
        },
    )
    assert resp.status_code == 422  # Pydantic validator


@pytest.mark.asyncio
async def test_create_order_kis_rejection(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.order_cash.return_value = _order_rejected()
    resp = await app_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "limit",
            "quantity": 1,
            "price": 5000,
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == "ORDER_FAILED"
    assert "상하한가" in body["message"]


# ---------------------------------------------------------------------------
# Safety gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_amount_cap_rejects_expensive_limit_order(
    low_cap_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """Cap = 5,000 KRW; submitting 2 × 10_000 = 20_000 must be blocked."""
    resp = await low_cap_client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "limit",
            "quantity": 2,
            "price": 10_000,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "ORDER_AMOUNT_EXCEEDED"
    fake_kis_client.order_cash.assert_not_called()


@pytest.mark.asyncio
async def test_real_mode_gate_blocks_create(
    real_mode_client: tuple[AsyncClient, Settings],
    fake_kis_client: FakeKISClient,
) -> None:
    client, _ = real_mode_client
    resp = await client.post(
        "/api/v1/orders",
        json={
            "symbol": "005930",
            "side": "buy",
            "order_type": "limit",
            "quantity": 1,
            "price": 1000,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TRADING_DISABLED"
    fake_kis_client.order_cash.assert_not_called()


@pytest.mark.asyncio
async def test_real_mode_gate_blocks_cancel(
    real_mode_client: tuple[AsyncClient, Settings],
    fake_kis_client: FakeKISClient,
) -> None:
    client, _ = real_mode_client
    resp = await client.delete("/api/v1/orders/01234-0000012345")
    assert resp.status_code == 403
    assert resp.json()["code"] == "TRADING_DISABLED"
    fake_kis_client.order_revise_cancel.assert_not_called()


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_orders_returns_composite_ids(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    """Regression for Phase 2 code review HIGH #1:
    list must return the composite `{branch}-{odno}` id so the frontend's
    subsequent cancel/modify call carries both halves back to KIS."""
    fake_kis_client.inquire_daily_ccld.return_value = _daily_ccld(
        [
            _exec_row(odno="0000012345"),
            _exec_row(odno="0000022222", filled="1"),
        ]
    )
    resp = await app_client.get("/api/v1/orders")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["orders"][0]["order_id"] == "01234-0000012345"
    assert body["orders"][1]["order_id"] == "01234-0000022222"
    assert body["orders"][0]["status"] == "submitted"
    assert body["orders"][1]["status"] == "filled"
    assert body["orders"][0]["name"] == "삼성전자"


@pytest.mark.asyncio
async def test_list_orders_partial_and_cancelled(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_ccld.return_value = _daily_ccld(
        [
            _exec_row(odno="0000000001", quantity="5", filled="2"),
            _exec_row(odno="0000000002", cancelled="Y"),
        ]
    )
    resp = await app_client.get("/api/v1/orders")
    assert resp.status_code == 200
    statuses = {row["order_id"]: row["status"] for row in resp.json()["orders"]}
    assert statuses["01234-0000000001"] == "partial"
    assert statuses["01234-0000000002"] == "cancelled"


@pytest.mark.asyncio
async def test_get_single_order_by_composite_id(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_ccld.return_value = _daily_ccld([_exec_row(odno="0000012345")])
    resp = await app_client.get("/api/v1/orders/01234-0000012345")
    assert resp.status_code == 200
    assert resp.json()["order_id"] == "01234-0000012345"


@pytest.mark.asyncio
async def test_get_single_order_by_bare_odno(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_ccld.return_value = _daily_ccld([_exec_row(odno="0000012345")])
    resp = await app_client.get("/api/v1/orders/0000012345")
    assert resp.status_code == 200
    # The response still uses the composite form sourced from the row.
    assert resp.json()["order_id"] == "01234-0000012345"


@pytest.mark.asyncio
async def test_get_single_order_not_found(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_daily_ccld.return_value = _daily_ccld([])
    resp = await app_client.get("/api/v1/orders/0000099999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "ORDER_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_order_rejects_injection_patterns(app_client: AsyncClient) -> None:
    """Regression for Phase 2 security review HIGH: path regex must
    reject non-numeric / control-char / overly-long order ids before
    they reach the KIS request body."""
    bad_ids = [
        "abc",  # letters
        "12345678901",  # 11 digits (too long)
        "123-",  # trailing separator
        "-12345",  # leading separator
        "01234-abcdef",  # non-numeric odno
        "01234 - 001",  # whitespace
    ]
    for bad in bad_ids:
        resp = await app_client.get(f"/api/v1/orders/{bad}")
        assert resp.status_code in (404, 422), f"{bad=} → {resp.status_code}"


# ---------------------------------------------------------------------------
# Cancel / Modify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_order(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.order_revise_cancel.return_value = _order_ok()
    resp = await app_client.delete("/api/v1/orders/01234-0000012345")
    assert resp.status_code == 200
    assert resp.json() == {"order_id": "01234-0000012345", "cancelled": True}

    call = fake_kis_client.order_revise_cancel.call_args.kwargs
    assert call["krx_fwdg_ord_orgno"] == "01234"
    assert call["original_order_id"] == "0000012345"
    assert call["operation"] == "cancel"


@pytest.mark.asyncio
async def test_modify_order_returns_narrow_response(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    """Regression for Phase 2 code review HIGH #2: modify must NOT
    fabricate symbol/side/order_type — the response is a deliberately
    narrow shape with only the fields KIS actually echoes."""
    fake_kis_client.order_revise_cancel.return_value = _order_ok(odno="0000033333")
    resp = await app_client.patch(
        "/api/v1/orders/01234-0000012345",
        json={"quantity": 1, "price": 7000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_id"] == "01234-0000033333"
    assert body["price"] == 7000
    assert body["quantity"] == 1
    assert "submitted_at" in body
    assert body["account_mode"] == "mock"
    assert "symbol" not in body
    assert "side" not in body
    assert "name" not in body

    call = fake_kis_client.order_revise_cancel.call_args.kwargs
    assert call["operation"] == "modify"
    assert call["quantity"] == 1
    assert call["price"] == 7000


@pytest.mark.asyncio
async def test_modify_order_amount_cap(low_cap_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    """Modifying an order must re-check the amount cap."""
    resp = await low_cap_client.patch(
        "/api/v1/orders/01234-0000012345",
        json={"quantity": 10, "price": 1000},  # 10_000 > 5_000 cap
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "ORDER_AMOUNT_EXCEEDED"
    fake_kis_client.order_revise_cancel.assert_not_called()
