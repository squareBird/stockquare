"""Stocks domain models (Pydantic)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class StockMarket(str, Enum):
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"


class StockSearchItemResponse(BaseModel):
    symbol: str
    name: str
    market: StockMarket


class StockSearchResponse(BaseModel):
    items: list[StockSearchItemResponse]
    count: int
