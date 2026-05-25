"""Portfolio endpoints — account summary and holdings."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_kis_client
from app.core.exceptions import KISAPIError, KISNotConfiguredError
from app.kis.client import KISClient
from app.models.portfolio import (
    AccountSummaryResponse,
    Holding,
    HoldingsResponse,
    PortfolioFieldError,
)
from app.services.portfolio import PortfolioHoldingsService, PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _get_service(kis: KISClient = Depends(get_kis_client)) -> PortfolioService:
    return PortfolioService(kis=kis)


def _get_holdings_service(
    kis: KISClient = Depends(get_kis_client),
) -> PortfolioHoldingsService:
    return PortfolioHoldingsService(kis=kis)


@router.get("/summary", response_model=AccountSummaryResponse)
async def account_summary(
    service: PortfolioService = Depends(_get_service),
) -> AccountSummaryResponse:
    summary = await service.get_account_summary()

    # When every KIS data source failed, escalate. Partial success drops
    # through and returns 200 with the available fields + `errors[]`.
    if summary.all_failed:
        if all(err.error_code == "KIS_NOT_CONFIGURED" for err in summary.errors):
            raise KISNotConfiguredError([])
        raise KISAPIError()

    return AccountSummaryResponse(
        total_asset=summary.total_asset,
        total_purchase=summary.total_purchase,
        total_profit=summary.total_profit,
        total_profit_rate=summary.total_profit_rate,
        daily_profit=summary.daily_profit,
        daily_profit_rate=summary.daily_profit_rate,
        cash_balance=summary.cash_balance,
        holdings_count=summary.holdings_count,
        errors=[
            PortfolioFieldError(
                field=err.field,
                error_code=err.error_code,
                message=err.message,
            )
            for err in summary.errors
        ],
    )


@router.get("/holdings", response_model=HoldingsResponse)
async def holdings(
    service: PortfolioHoldingsService = Depends(_get_holdings_service),
) -> HoldingsResponse:
    """Per-symbol holdings with live KIS pricing.

    Empty holdings with a healthy KIS call returns `200` with an empty
    list. A failed upstream KIS call escalates to the corresponding HTTP
    status (`503` for `KIS_NOT_CONFIGURED`, `502` for everything else) so
    the frontend can distinguish a truly empty portfolio from an outage.
    """
    result = await service.get_holdings()

    if result.errors and not result.holdings:
        # Total failure — decide 503 vs 502 based on the underlying cause.
        if all(err.error_code == "KIS_NOT_CONFIGURED" for err in result.errors):
            raise KISNotConfiguredError([])
        raise KISAPIError()

    return HoldingsResponse(
        holdings=[
            Holding(
                symbol=item.symbol,
                name=item.name,
                quantity=item.quantity,
                avg_purchase_price=item.avg_purchase_price,
                current_price=item.current_price,
                evaluation_amount=item.evaluation_amount,
                purchase_amount=item.purchase_amount,
                profit=item.profit,
                profit_rate=item.profit_rate,
            )
            for item in result.holdings
        ],
        errors=[
            PortfolioFieldError(
                field=err.field,
                error_code=err.error_code,
                message=err.message,
            )
            for err in result.errors
        ],
        count=len(result.holdings) + len(result.errors),
    )
