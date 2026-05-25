"""Stocks business logic — symbol search and classification."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.exceptions import InvalidQueryError, InvalidSymbolError, KISAPIError
from app.kis.client import KISClient
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
