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


class ChartInterval(str, Enum):
    """Candle granularity for the price chart.

    Selects how each candle is aggregated, not a lookback window — the
    visible range is derived per interval (see ``StocksService.get_history``).
    ``MINUTE`` uses the intraday endpoint; the rest share the daily endpoint
    with a KIS period-division code (D/W/M).
    """

    MINUTE = "min"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class Candle(BaseModel):
    # ISO date (YYYY-MM-DD) for day/week/month candles; epoch seconds (int) for
    # intraday minute candles. lightweight-charts accepts both forms directly.
    time: str | int
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistoryResponse(BaseModel):
    symbol: str
    interval: ChartInterval
    candles: list[Candle]


class RankBy(str, Enum):
    """Market-wide ranking dimension for `StocksService.rank_stocks`."""

    FLUCTUATION = "fluctuation"
    VOLUME = "volume"


class RankDirection(str, Enum):
    """Sort direction for fluctuation ranking (rising vs falling)."""

    UP = "up"
    DOWN = "down"


class RankedStock(BaseModel):
    symbol: str
    name: str
    price: int
    change_rate: float
    volume: int | None = None
