"""Portfolio endpoints — account summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_kis_client
from app.core.exceptions import KISAPIError, KISNotConfiguredError
from app.kis.client import KISClient
from app.models.portfolio import AccountSummaryResponse, PortfolioFieldError
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _get_service(kis: KISClient = Depends(get_kis_client)) -> PortfolioService:
    return PortfolioService(kis=kis)


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
