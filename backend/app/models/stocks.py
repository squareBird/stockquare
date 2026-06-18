"""Stocks domain models (Pydantic)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class StockMarket(str, Enum):
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    AMEX = "AMEX"


class StockSearchItemResponse(BaseModel):
    symbol: str
    name: str
    market: StockMarket


class StockSearchResponse(BaseModel):
    items: list[StockSearchItemResponse]
    count: int


class ChartPeriod(str, Enum):
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    THREE_MONTH = "3m"
    ONE_YEAR = "1y"


class Candle(BaseModel):
    time: str  # ISO date (YYYY-MM-DD) for daily candles
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistoryResponse(BaseModel):
    symbol: str
    period: ChartPeriod
    candles: list[Candle]
