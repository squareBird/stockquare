"""Tests for /api/v1/portfolio endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import KISAPIError, KISNotConfiguredError
from app.kis.models import (
    AccountBalanceHolding,
    AccountBalanceResponse,
    AccountBalanceSummary,
    AccountSummaryOutput,
    AccountSummaryResponse,
)
from tests.conftest import FakeKISClient


def _summary_response(total: str = "15230000", daily: str = "120000") -> AccountSummaryResponse:
    return AccountSummaryResponse(
        rt_cd="0",
        output2=AccountSummaryOutput(
            tot_asst_amt=total,
            pchs_amt_smtl="14500000",
            evlu_pfls_smtl="730000",
            evlu_pfls_rt="5.03",
            bfdy_cprs_pfls=daily,
        ),
    )


def _balance_response(holdings: int = 2, cash: str = "3200000") -> AccountBalanceResponse:
    return AccountBalanceResponse(
        rt_cd="0",
        output1=[
            AccountBalanceHolding(pdno=f"00000{i}", prdt_name=f"Stock {i}", hldg_qty="10") for i in range(holdings)
        ],
        output2=[AccountBalanceSummary(dnca_tot_amt=cash)],
    )


def _holdings_balance_response() -> AccountBalanceResponse:
    """Richer balance response populating every holding field we project."""
    return AccountBalanceResponse(
        rt_cd="0",
        output1=[
            AccountBalanceHolding(
                pdno="005930",
                prdt_name="삼성전자",
                hldg_qty="10",
                pchs_avg_pric="71000",
                prpr="72300",
                evlu_amt="723000",
                pchs_amt="710000",
                evlu_pfls_amt="13000",
                evlu_pfls_rt="1.83",
            ),
            AccountBalanceHolding(
                pdno="000660",
                prdt_name="SK하이닉스",
                hldg_qty="5",
                pchs_avg_pric="145000",
                prpr="148500",
                evlu_amt="742500",
                pchs_amt="725000",
                evlu_pfls_amt="17500",
                evlu_pfls_rt="2.41",
            ),
            AccountBalanceHolding(
                pdno="000001",
                prdt_name="유령종목",
                hldg_qty="0",
                pchs_avg_pric="0",
                prpr="0",
                evlu_amt="0",
                pchs_amt="0",
                evlu_pfls_amt="0",
                evlu_pfls_rt="0",
            ),
        ],
        output2=[AccountBalanceSummary(dnca_tot_amt="3200000")],
    )


@pytest.mark.asyncio
async def test_account_summary_full_success(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_account_summary.return_value = _summary_response()
    fake_kis_client.inquire_balance.return_value = _balance_response()

    response = await app_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_asset"] == 15230000
    assert body["total_profit"] == 730000
    assert body["cash_balance"] == 3200000
    assert body["holdings_count"] == 2
    assert body["daily_profit"] == 120000
    assert body["daily_profit_rate"] == pytest.approx(0.79, abs=0.01)
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_account_summary_handles_zero_total(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_account_summary.return_value = _summary_response(total="0", daily="0")
    fake_kis_client.inquire_balance.return_value = _balance_response(holdings=0, cash="0")

    response = await app_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["daily_profit_rate"] == 0.0
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_account_summary_partial_failure_balance_down(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """When `inquire-balance` fails but the account summary succeeds,
    surface the account fields and null the balance-sourced fields."""
    fake_kis_client.inquire_account_summary.return_value = _summary_response()
    fake_kis_client.inquire_balance.side_effect = KISAPIError()

    response = await app_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_asset"] == 15230000
    assert body["total_profit"] == 730000
    assert body["daily_profit_rate"] == pytest.approx(0.79, abs=0.01)
    assert body["cash_balance"] is None
    assert body["holdings_count"] is None
    error_fields = {err["field"] for err in body["errors"]}
    assert error_fields == {"cash_balance", "holdings_count"}
    for err in body["errors"]:
        assert err["error_code"] == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_account_summary_partial_failure_summary_down(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """When `inquire-account-balance` fails but the balance call succeeds,
    surface the balance fields and null the summary-sourced fields."""
    fake_kis_client.inquire_account_summary.side_effect = KISAPIError()
    fake_kis_client.inquire_balance.return_value = _balance_response()

    response = await app_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == 3200000
    assert body["holdings_count"] == 2
    assert body["total_asset"] is None
    assert body["total_profit"] is None
    assert body["daily_profit_rate"] is None
    error_fields = {err["field"] for err in body["errors"]}
    assert error_fields == {
        "total_asset",
        "total_purchase",
        "total_profit",
        "total_profit_rate",
        "daily_profit",
    }


@pytest.mark.asyncio
async def test_account_summary_full_failure_returns_502(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    fake_kis_client.inquire_account_summary.side_effect = KISAPIError()
    fake_kis_client.inquire_balance.side_effect = KISAPIError()
    resp = await app_client.get("/api/v1/portfolio/summary")
    assert resp.status_code == 502
    assert resp.json()["code"] == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_account_summary_full_failure_missing_credentials_returns_503(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    """When both data sources fail because of missing credentials, preserve
    the 503 KIS_NOT_CONFIGURED semantic instead of collapsing to 502."""
    fake_kis_client.inquire_account_summary.side_effect = KISNotConfiguredError(["KIS_APP_KEY", "KIS_APP_SECRET"])
    fake_kis_client.inquire_balance.side_effect = KISNotConfiguredError(["KIS_APP_KEY", "KIS_APP_SECRET"])
    resp = await app_client.get("/api/v1/portfolio/summary")
    assert resp.status_code == 503
    assert resp.json()["code"] == "KIS_NOT_CONFIGURED"


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portfolio_holdings_returns_mapped_rows(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_balance.return_value = _holdings_balance_response()
    resp = await app_client.get("/api/v1/portfolio/holdings")
    assert resp.status_code == 200
    body = resp.json()
    # Zero-quantity row should be filtered.
    assert body["count"] == 2
    assert len(body["holdings"]) == 2
    assert body["errors"] == []

    samsung = body["holdings"][0]
    assert samsung["symbol"] == "005930"
    assert samsung["name"] == "삼성전자"
    assert samsung["quantity"] == 10
    assert samsung["avg_purchase_price"] == 71000
    assert samsung["current_price"] == 72300
    assert samsung["evaluation_amount"] == 723000
    assert samsung["purchase_amount"] == 710000
    assert samsung["profit"] == 13000
    assert samsung["profit_rate"] == pytest.approx(1.83)


@pytest.mark.asyncio
async def test_portfolio_holdings_empty_when_no_rows(app_client: AsyncClient, fake_kis_client: FakeKISClient) -> None:
    fake_kis_client.inquire_balance.return_value = AccountBalanceResponse(
        rt_cd="0",
        output1=[],
        output2=[],
    )
    resp = await app_client.get("/api/v1/portfolio/holdings")
    assert resp.status_code == 200
    assert resp.json() == {"holdings": [], "errors": [], "count": 0}


@pytest.mark.asyncio
async def test_portfolio_holdings_kis_failure_returns_502(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    fake_kis_client.inquire_balance.side_effect = KISAPIError()
    resp = await app_client.get("/api/v1/portfolio/holdings")
    assert resp.status_code == 502
    assert resp.json()["code"] == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_portfolio_holdings_missing_credentials_returns_503(
    app_client: AsyncClient, fake_kis_client: FakeKISClient
) -> None:
    fake_kis_client.inquire_balance.side_effect = KISNotConfiguredError(["KIS_APP_KEY", "KIS_APP_SECRET"])
    resp = await app_client.get("/api/v1/portfolio/holdings")
    assert resp.status_code == 503
    assert resp.json()["code"] == "KIS_NOT_CONFIGURED"
