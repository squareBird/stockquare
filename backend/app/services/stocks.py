"""Stocks business logic — symbol search and classification."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.exceptions import InvalidQueryError, InvalidSymbolError, KISAPIError
from app.kis.client import KISClient
from app.kis.models import DailyChartCandle
from app.models.stocks import Candle, ChartPeriod
from app.services.stock_index import StockMasterIndex, StockMasterRow

logger = logging.getLogger(__name__)

SYMBOL_PATTERN = re.compile(r"^\d{6}$")

# KIS market identifier codes → our canonical market label.
_KIS_MARKET_CODE_MAP = {
    "STK": "KOSPI",
    "KSP": "KOSPI",
    "KSQ": "KOSDAQ",
    "KDQ": "KOSDAQ",
    "KNX": "KOSDAQ",
}


@dataclass
class StockSearchItem:
    symbol: str
    name: str
    market: str


def _classify_market(code: str) -> str:
    return _KIS_MARKET_CODE_MAP.get(code, "KOSPI")


def _display_name(row: StockMasterRow) -> str:
    """Prefer Korean name, fall back to English, then to the ticker."""
    if row.name_ko:
        return row.name_ko
    if row.name_en:
        return row.name_en
    return row.symbol


# Lookback windows (calendar days) per chart period. KIS returns only trading
# days inside the window, so calendar-day spans are sufficient.
_PERIOD_WINDOW_DAYS: dict[ChartPeriod, int] = {
    ChartPeriod.ONE_WEEK: 7,
    ChartPeriod.ONE_MONTH: 31,
    ChartPeriod.THREE_MONTH: 93,
    ChartPeriod.ONE_YEAR: 366,
}


def _format_chart_date(yyyymmdd: str) -> str:
    """Convert a KIS `YYYYMMDD` business date to an ISO `YYYY-MM-DD` string."""
    return f"{yyyymmdd[0:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def _to_candle(row: DailyChartCandle) -> Candle:
    return Candle(
        time=_format_chart_date(row.date),
        open=float(row.open or "0"),
        high=float(row.high or "0"),
        low=float(row.low or "0"),
        close=float(row.close or "0"),
        volume=int(float(row.volume or "0")),
    )


class StocksService:
    """Business logic for stock search / metadata lookups."""

    def __init__(self, kis: KISClient, index: StockMasterIndex) -> None:
        self._kis = kis
        self._index = index

    async def search_stocks(self, query: str, limit: int) -> list[StockSearchItem]:
        query = query.strip()
        if not query:
            raise InvalidQueryError()

        # 6-digit KR codes go through the live KIS quote path so we
        # return the authoritative HTS name from inquire-price rather
        # than the master-file snapshot (which can lag a day).
        if SYMBOL_PATTERN.match(query):
            return await self._search_kr_symbol(query, limit)

        # Text queries are served from the in-memory index. If the
        # startup refresh failed, the index is empty and we return an
        # empty list rather than a 502 — the search box must never
        # show a red error state for a legitimate empty result.
        rows = self._index.search(query, limit)
        return [
            StockSearchItem(
                symbol=row.symbol,
                name=_display_name(row),
                market=row.market.value,
            )
            for row in rows
        ]

    async def _search_kr_symbol(self, query: str, limit: int) -> list[StockSearchItem]:
        try:
            price_resp = await self._kis.inquire_stock_price(query)
        except InvalidSymbolError:
            return []
        # Use search_info for a reliable market classification.
        market = "KOSPI"
        try:
            info_resp = await self._kis.search_info(query)
            if info_resp.rt_cd == "0":
                market = _classify_market(info_resp.output.market_code)
        except KISAPIError as exc:
            logger.warning(
                "stock search-info lookup failed",
                extra={"symbol": query, "exc_type": type(exc).__name__},
            )
        item = StockSearchItem(
            symbol=query,
            name=price_resp.output.name or query,
            market=market,
        )
        return [item][:limit]

    async def get_history(self, symbol: str, period: ChartPeriod) -> list[Candle]:
        """Return the daily OHLCV candle series for a 6-digit KR symbol.

        Candles are ordered oldest -> newest. An unknown symbol raises
        InvalidSymbolError (400); an empty window returns an empty list.
        """
        symbol = symbol.strip()
        if not SYMBOL_PATTERN.match(symbol):
            raise InvalidSymbolError(symbol)

        now_kst = datetime.now(UTC) + timedelta(hours=9)
        to_date = now_kst.strftime("%Y%m%d")
        from_date = (now_kst - timedelta(days=_PERIOD_WINDOW_DAYS[period])).strftime("%Y%m%d")

        resp = await self._kis.inquire_daily_itemchartprice(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
        )
        # KIS returns rows newest-first and pads short windows with blank-date
        # entries; reverse to oldest-first and drop the padding rows.
        return [_to_candle(row) for row in reversed(resp.output2) if row.date]
