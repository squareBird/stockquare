"""Stocks business logic — symbol search and classification."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.core.exceptions import InvalidQueryError, InvalidSymbolError, KISAPIError
from app.kis.client import KISClient

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


class StocksService:
    """Business logic for stock search / metadata lookups."""

    def __init__(self, kis: KISClient) -> None:
        self._kis = kis

    async def search_stocks(self, query: str, limit: int) -> list[StockSearchItem]:
        query = query.strip()
        if not query:
            raise InvalidQueryError()

        items: list[StockSearchItem] = []
        if SYMBOL_PATTERN.match(query):
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
            items.append(
                StockSearchItem(
                    symbol=query,
                    name=price_resp.output.name or query,
                    market=market,
                )
            )
            return items[:limit]

        # Text query: KIS search-info returns a single product by name match.
        # Phase 1 delegates richer fuzzy search to a later phase.
        try:
            resp = await self._kis.search_info(query)
            if resp.rt_cd == "0" and resp.output.symbol:
                items.append(
                    StockSearchItem(
                        symbol=resp.output.symbol,
                        name=resp.output.name,
                        market=_classify_market(resp.output.market_code),
                    )
                )
        except KISAPIError as exc:
            logger.warning(
                "stock search failed",
                extra={"query": query, "exc_type": type(exc).__name__},
            )
        return items[:limit]
