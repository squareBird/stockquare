"""Portfolio domain models (Pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioFieldError(BaseModel):
    """Per-data-source failure surface for portfolio endpoints.

    `field` is the canonical portfolio field name (or the upstream KIS call
    identifier) the frontend can use to render a degraded skeleton for that
    specific stat while keeping healthy siblings.
    """

    field: str
    error_code: str
    message: str


class AccountSummaryResponse(BaseModel):
    # Sourced from `inquire-account-balance`
    total_asset: int | None = None
    total_purchase: int | None = None
    total_profit: int | None = None
    total_profit_rate: float | None = None
    daily_profit: int | None = None
    daily_profit_rate: float | None = None
    # Sourced from `inquire-balance`
    cash_balance: int | None = None
    holdings_count: int | None = None
    # Per-data-source failures. Empty list means both KIS calls succeeded.
    errors: list[PortfolioFieldError] = Field(default_factory=list)


class Holding(BaseModel):
    """Single stock holding row.

    Derived from KIS `inquire-balance` output1. Amounts are integer KRW —
    KIS returns fractional values for fund positions but this schema is
    scoped to direct stock holdings where whole-won values are canonical.
    """

    symbol: str
    name: str
    quantity: int
    avg_purchase_price: int
    current_price: int
    evaluation_amount: int
    purchase_amount: int
    profit: int
    profit_rate: float


class HoldingsResponse(BaseModel):
    holdings: list[Holding]
    errors: list[PortfolioFieldError] = Field(default_factory=list)
    count: int
