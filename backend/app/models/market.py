"""Market domain models (Pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.kis.models import MarketStatus


class MarketIndexResponse(BaseModel):
    code: str
    name: str
    value: float
    change: float
    change_rate: float
    volume: int
    status: MarketStatus


class MarketIndexErrorResponse(BaseModel):
    code: str
    name: str
    error_code: str
    message: str


class MarketIndicesResponse(BaseModel):
    indices: list[MarketIndexResponse]
    # Per-index failures. Empty list means every index was healthy. The
    # frontend can render an error skeleton for each entry here while still
    # showing the healthy cards from `indices`.
    errors: list[MarketIndexErrorResponse] = Field(default_factory=list)
