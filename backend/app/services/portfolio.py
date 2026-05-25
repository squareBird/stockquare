"""Portfolio business logic — account summary and holdings."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.core.exceptions import KISAPIError, StockquareError
from app.kis.client import KISClient
from app.kis.models import AccountBalanceResponse, AccountSummaryResponse
from app.services._helpers import to_float, to_int

logger = logging.getLogger(__name__)


@dataclass
class Holding:
    symbol: str
    name: str
    quantity: int
    avg_purchase_price: int
    current_price: int
    evaluation_amount: int
    purchase_amount: int
    profit: int
    profit_rate: float


@dataclass
class HoldingsResult:
    holdings: list[Holding]
    errors: list[PortfolioFieldFailure]


@dataclass
class PortfolioFieldFailure:
    field: str
    error_code: str
    message: str


@dataclass
class AccountSummary:
    """Partial-failure-safe bundle for the portfolio summary.

    Each numeric field is `None` when the upstream KIS data source for
    that field failed. `errors` lists the failures so the frontend can
    render a per-field degraded skeleton.
    """

    total_asset: int | None = None
    total_purchase: int | None = None
    total_profit: int | None = None
    total_profit_rate: float | None = None
    daily_profit: int | None = None
    daily_profit_rate: float | None = None
    cash_balance: int | None = None
    holdings_count: int | None = None
    errors: list[PortfolioFieldFailure] = field(default_factory=list)

    @property
    def all_failed(self) -> bool:
        """True when every KIS data source failed."""
        populated = any(
            value is not None
            for value in (
                self.total_asset,
                self.total_purchase,
                self.total_profit,
                self.total_profit_rate,
                self.daily_profit,
                self.cash_balance,
                self.holdings_count,
            )
        )
        return not populated and bool(self.errors)


class PortfolioService:
    """Business logic for portfolio-level endpoints."""

    def __init__(self, kis: KISClient) -> None:
        self._kis = kis

    async def get_account_summary(self) -> AccountSummary:
        """Fetch the portfolio summary with per-data-source graceful degradation.

        Two KIS calls back the response:

        1. `inquire-account-balance` →
           `total_asset / total_purchase / total_profit / total_profit_rate / daily_profit`
        2. `inquire-balance` → `cash_balance / holdings_count`

        If only one call fails the healthy data still surfaces with its
        siblings set to `None` and a matching entry appended to `errors`.
        The caller returns HTTP 200 in that case and only escalates to an
        upstream error when both calls fail.
        """
        summary_resp, balance_resp = await asyncio.gather(
            self._kis.inquire_account_summary(),
            self._kis.inquire_balance(),
            return_exceptions=True,
        )

        result = AccountSummary()
        total_asset_for_rate: int | None = None

        if isinstance(summary_resp, AccountSummaryResponse):
            summary_output = summary_resp.output2
            if summary_output is not None:
                result.total_asset = to_int(summary_output.total_asset)
                result.total_purchase = to_int(summary_output.total_purchase)
                result.total_profit = to_int(summary_output.total_profit)
                result.total_profit_rate = to_float(summary_output.total_profit_rate)
                result.daily_profit = to_int(summary_output.daily_profit)
                total_asset_for_rate = result.total_asset
        elif isinstance(summary_resp, BaseException):
            error_code, message = _classify_error(summary_resp)
            logger.warning(
                "portfolio account-summary fetch failed",
                extra={"error_code": error_code},
            )
            for field_name in (
                "total_asset",
                "total_purchase",
                "total_profit",
                "total_profit_rate",
                "daily_profit",
            ):
                result.errors.append(
                    PortfolioFieldFailure(
                        field=field_name,
                        error_code=error_code,
                        message=message,
                    )
                )

        if isinstance(balance_resp, AccountBalanceResponse):
            if balance_resp.output2:
                result.cash_balance = to_int(balance_resp.output2[0].cash_balance)
            else:
                result.cash_balance = 0
            result.holdings_count = len(balance_resp.output1)
        elif isinstance(balance_resp, BaseException):
            error_code, message = _classify_error(balance_resp)
            logger.warning(
                "portfolio balance fetch failed",
                extra={"error_code": error_code},
            )
            for field_name in ("cash_balance", "holdings_count"):
                result.errors.append(
                    PortfolioFieldFailure(
                        field=field_name,
                        error_code=error_code,
                        message=message,
                    )
                )

        # `daily_profit_rate` is derived; only populate it when both inputs
        # are available.
        if result.daily_profit is not None and total_asset_for_rate is not None:
            if total_asset_for_rate > 0:
                result.daily_profit_rate = round((result.daily_profit / total_asset_for_rate) * 100, 2)
            else:
                result.daily_profit_rate = 0.0

        return result


def _classify_error(exc: BaseException) -> tuple[str, str]:
    """Translate an exception into a (code, message) tuple."""
    if isinstance(exc, StockquareError):
        return exc.code, exc.message
    return "UNKNOWN_ERROR", type(exc).__name__


# ---------------------------------------------------------------------------
# Holdings — per-symbol detail view
# ---------------------------------------------------------------------------


class PortfolioHoldingsService:
    """Business logic for the per-symbol holdings list.

    Reuses the `inquire-balance` KIS call (same one that feeds
    `PortfolioService.get_account_summary`) but projects `output1` rows
    into the richer `Holding` view instead of just counting them.
    """

    def __init__(self, kis: KISClient) -> None:
        self._kis = kis

    async def get_holdings(self) -> HoldingsResult:
        try:
            balance_resp = await self._kis.inquire_balance()
        except KISAPIError as exc:
            error_code, message = _classify_error(exc)
            logger.warning(
                "portfolio holdings fetch failed",
                extra={"error_code": error_code},
            )
            return HoldingsResult(
                holdings=[],
                errors=[
                    PortfolioFieldFailure(
                        field="holdings",
                        error_code=error_code,
                        message=message,
                    )
                ],
            )

        holdings: list[Holding] = []
        for row in balance_resp.output1:
            quantity = to_int(row.quantity)
            if quantity <= 0:
                # Fully liquidated rows can linger in KIS responses.
                continue
            holdings.append(
                Holding(
                    symbol=row.symbol,
                    name=row.name or row.symbol,
                    quantity=quantity,
                    avg_purchase_price=to_int(row.avg_purchase_price),
                    current_price=to_int(row.current_price),
                    evaluation_amount=to_int(row.evaluation_amount),
                    purchase_amount=to_int(row.purchase_amount),
                    profit=to_int(row.profit),
                    profit_rate=to_float(row.profit_rate),
                )
            )
        return HoldingsResult(holdings=holdings, errors=[])
