"""Watchlist domain models (Pydantic)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WatchlistAddRequest(BaseModel):
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class WatchlistOrderItem(BaseModel):
    id: int
    sort_order: int = Field(ge=0)


class WatchlistReorderRequest(BaseModel):
    order: list[WatchlistOrderItem]


class WatchlistItemCreatedResponse(BaseModel):
    id: int
    symbol: str
    name: str
    sort_order: int
    created_at: datetime


class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    name: str
    price: int
    change: int
    change_rate: float
    volume: int
    sort_order: int
    created_at: datetime


class WatchlistItemError(BaseModel):
    """Per-item failure surface for `/api/v1/watchlist` degraded reads."""

    id: int
    symbol: str
    sort_order: int
    error_code: str
    message: str


class WatchlistResponse(BaseModel):
    items: list[WatchlistItemResponse]
    # Per-item enrichment failures. Empty list means every item surfaced a
    # live KIS quote. Entries here are items the frontend should render in a
    # degraded skeleton instead of dropping from the watchlist entirely.
    errors: list[WatchlistItemError] = Field(default_factory=list)
    count: int


class WatchlistReorderResponse(BaseModel):
    updated: int
