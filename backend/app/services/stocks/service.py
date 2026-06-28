"""Stocks business logic — symbol search and classification."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from app.core.exceptions import InvalidQueryError, InvalidSymbolError, KISAPIError
from app.kis.client import KISClient
from app.kis.models import DailyChartCandle, MinuteChartCandle, RankingRow
from app.models.stocks import (
    Candle,
    ChartInterval,
    RankBy,
    RankDirection,
    RankedStock,
)
from app.services._helpers import to_float, to_int
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


# Visible lookback windows (calendar days) per day-family interval. KIS returns
# only trading days inside the window, so calendar-day spans are sufficient. The
# window scales with the candle granularity: enough daily candles for ~6 months,
# weekly for ~2 years, monthly for ~5 years (per CHARTS.md).
_INTERVAL_WINDOW_DAYS: dict[ChartInterval, int] = {
    ChartInterval.DAY: 186,
    ChartInterval.WEEK: 731,
    ChartInterval.MONTH: 1827,
}

# KIS `FID_PERIOD_DIV_CODE` for the day-family intervals (daily endpoint).
_INTERVAL_PERIOD_CODE: dict[ChartInterval, str] = {
    ChartInterval.DAY: "D",
    ChartInterval.WEEK: "W",
    ChartInterval.MONTH: "M",
}

# Intraday paging guard: one trading session is ~6.5h = 390 minute candles, and
# KIS returns ~30 per page. Cap the back-paging so a clock/holiday edge case
# can't loop unbounded.
_MINUTE_MAX_PAGES = 16


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


# KST is UTC+9; KIS intraday date/time are KST wall-clock with no offset, so we
# attach +09:00 explicitly to produce a correct absolute epoch.
_KST = timezone(timedelta(hours=9))


def _minute_epoch(date_yyyymmdd: str, time_hhmmss: str) -> int:
    """Convert a KIS intraday `YYYYMMDD` + `HHMMSS` (KST) pair to epoch seconds."""
    dt = datetime(
        int(date_yyyymmdd[0:4]),
        int(date_yyyymmdd[4:6]),
        int(date_yyyymmdd[6:8]),
        int(time_hhmmss[0:2]),
        int(time_hhmmss[2:4]),
        int(time_hhmmss[4:6]),
        tzinfo=_KST,
    )
    return int(dt.timestamp())


def _hhmmss_minus_one_second(hhmmss: str) -> str | None:
    """Return `HHMMSS` one second earlier, or None if it would underflow 00:00:00.

    Used to advance the intraday paging anchor below the oldest candle already
    fetched so KIS returns strictly older bars on the next page.
    """
    h, m, s = int(hhmmss[0:2]), int(hhmmss[2:4]), int(hhmmss[4:6])
    total = h * 3600 + m * 60 + s - 1
    if total < 0:
        return None
    return f"{total // 3600:02d}{(total % 3600) // 60:02d}{total % 60:02d}"


def _to_minute_candle(row: MinuteChartCandle) -> Candle:
    return Candle(
        time=_minute_epoch(row.date, row.time),
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
            await self._kis.inquire_stock_price(query)
        except InvalidSymbolError:
            return []
        # inquire-price validates the code but carries no stock name, so the
        # name and market both come from search-info (prdt_name / mket_id_cd).
        # Fall back to the master index, then the code, when search-info fails.
        name = ""
        market = "KOSPI"
        try:
            info_resp = await self._kis.search_info(query)
            if info_resp.rt_cd == "0":
                name = info_resp.output.name
                market = _classify_market(info_resp.output.market_code)
        except KISAPIError as exc:
            logger.warning(
                "stock search-info lookup failed",
                extra={"symbol": query, "exc_type": type(exc).__name__},
            )
        if not name:
            row = self._index.by_symbol(query)
            if row is not None:
                name = row.name_ko or row.name_en
        item = StockSearchItem(
            symbol=query,
            name=name or query,
            market=market,
        )
        return [item][:limit]

    async def get_quote(self, symbol: str) -> RankedStock:
        """Return the current price/change for a single 6-digit KR symbol.

        Reuses the ranking result shape (`RankedStock`) since it carries the
        same price/change fields. Raises InvalidSymbolError for a malformed or
        unknown code; KIS failures propagate as KISAPIError.
        """
        symbol = symbol.strip()
        if not SYMBOL_PATTERN.match(symbol):
            raise InvalidSymbolError(symbol)
        price = await self._kis.inquire_stock_price(symbol)
        out = price.output
        return RankedStock(
            symbol=symbol,
            name=self._resolve_name(symbol, out.name),
            price=to_int(out.price),
            change_rate=to_float(out.change_rate),
            volume=to_int(out.volume),
        )

    async def rank_stocks(
        self,
        *,
        by: RankBy,
        direction: RankDirection = RankDirection.UP,
        limit: int = 5,
    ) -> list[RankedStock]:
        """Return the top KRX stocks ranked by a market-wide condition.

        Used by the assistant's recommendation tool and any future screener.
        Names are resolved from the in-memory master index (same pattern as
        watchlist enrichment) rather than the KIS row name, falling back to
        the KIS name then the symbol. On KIS failure the underlying
        `KISAPIError` / `KISNotConfiguredError` propagates to the caller.

        Args:
            by: Ranking dimension — fluctuation (등락률) or volume (거래량).
            direction: For fluctuation, up = top gainers, down = top losers.
                Ignored for volume ranking.
            limit: Maximum rows to return (1-20).

        Returns:
            Up to ``limit`` ranked stocks, best first.
        """
        limit = max(1, min(limit, 20))
        if by == RankBy.VOLUME:
            resp = await self._kis.ranking_volume(count=limit)
        else:
            resp = await self._kis.ranking_fluctuation(
                rising=direction == RankDirection.UP,
                count=limit,
            )
        return [self._to_ranked_stock(row) for row in resp.output[:limit]]

    def _to_ranked_stock(self, row: RankingRow) -> RankedStock:
        name = self._resolve_name(row.symbol, row.name)
        return RankedStock(
            symbol=row.symbol,
            name=name,
            price=to_int(row.price),
            change_rate=to_float(row.change_rate),
            volume=to_int(row.volume),
        )

    def resolve_name(self, symbol: str, fallback: str = "") -> str:
        """Resolve a display name from the master index, then fallbacks.

        Public so callers that only have a symbol (e.g. the assistant chart
        tool) can label it without an extra KIS round-trip.
        """
        index_row = self._index.by_symbol(symbol)
        if index_row is not None:
            name = index_row.name_ko or index_row.name_en
            if name:
                return name
        return fallback or symbol

    # Backwards-compatible private alias (internal callers).
    _resolve_name = resolve_name

    async def get_history(
        self, symbol: str, interval: ChartInterval = ChartInterval.DAY
    ) -> list[Candle]:
        """Return the OHLCV candle series for a 6-digit KR symbol.

        The candle granularity is selected by ``interval``: ``MINUTE`` returns
        the current session's 1-minute candles (epoch-second ``time``); the
        day-family intervals (``DAY``/``WEEK``/``MONTH``) return date-stamped
        candles over an interval-scaled lookback window. Candles are ordered
        oldest -> newest. An unknown symbol raises InvalidSymbolError (400); an
        empty window returns an empty list.
        """
        symbol = symbol.strip()
        if not SYMBOL_PATTERN.match(symbol):
            raise InvalidSymbolError(symbol)

        if interval == ChartInterval.MINUTE:
            return await self._get_minute_history(symbol)
        return await self._get_daily_family_history(symbol, interval)

    async def _get_daily_family_history(
        self, symbol: str, interval: ChartInterval
    ) -> list[Candle]:
        """Daily/weekly/monthly candles via inquire-daily-itemchartprice."""
        now_kst = datetime.now(UTC) + timedelta(hours=9)
        to_date = now_kst.strftime("%Y%m%d")
        from_date = (
            now_kst - timedelta(days=_INTERVAL_WINDOW_DAYS[interval])
        ).strftime("%Y%m%d")

        resp = await self._kis.inquire_daily_itemchartprice(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            period_code=_INTERVAL_PERIOD_CODE[interval],
        )
        # KIS returns rows newest-first and pads short windows with blank-date
        # entries; reverse to oldest-first and drop the padding rows.
        return [_to_candle(row) for row in reversed(resp.output2) if row.date]

    async def _get_minute_history(self, symbol: str) -> list[Candle]:
        """Intraday 1-minute candles for the current session.

        KIS returns ~30 candles per page ending at an `HHMMSS` anchor; we page
        backwards from the current time until a page is empty or repeats, then
        sort the merged set oldest-first. Duplicate timestamps across page
        boundaries are de-duplicated.
        """
        now_kst = datetime.now(UTC) + timedelta(hours=9)
        anchor = now_kst.strftime("%H%M%S")

        by_epoch: dict[int, Candle] = {}
        for _ in range(_MINUTE_MAX_PAGES):
            resp = await self._kis.inquire_time_itemchartprice(symbol=symbol, to_time=anchor)
            rows = [row for row in resp.output2 if row.date and row.time]
            if not rows:
                break
            # rows are newest-first; the last is the oldest in this page.
            before = len(by_epoch)
            for row in rows:
                candle = _to_minute_candle(row)
                by_epoch[int(candle.time)] = candle
            # No new candles → we've reached the start of the session.
            if len(by_epoch) == before:
                break
            oldest_time = rows[-1].time
            # Step one second below the oldest candle so the next page does not
            # re-fetch it as its newest row.
            next_anchor = _hhmmss_minus_one_second(oldest_time)
            if next_anchor is None:
                break
            anchor = next_anchor

        return [by_epoch[key] for key in sorted(by_epoch)]
