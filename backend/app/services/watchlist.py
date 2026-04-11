"""Watchlist business logic — CRUD + KIS price enrichment."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateSymbolError,
    StockquareError,
    WatchlistFullError,
    WatchlistNotFoundError,
)
from app.db.models import Watchlist
from app.kis.client import KISClient
from app.kis.models import StockPriceResponse
from app.models.watchlist import (
    WatchlistItemCreatedResponse,
    WatchlistItemError,
    WatchlistItemResponse,
    WatchlistOrderItem,
)
from app.services._helpers import to_float, to_int

logger = logging.getLogger(__name__)

MAX_WATCHLIST_ITEMS = 20


@dataclass
class WatchlistEnrichmentResult:
    """Bundle of enriched successes + per-item errors for a list call."""

    items: list[WatchlistItemResponse]
    errors: list[WatchlistItemError]


class WatchlistService:
    """Business logic for watchlist CRUD and enrichment."""

    def __init__(self, session: AsyncSession, kis: KISClient) -> None:
        self._session = session
        self._kis = kis

    async def list_watchlist(self) -> WatchlistEnrichmentResult:
        """Return watchlist items enriched with live KIS price data.

        Successful KIS enrichments end up in `items` with the live Korean
        name (`hts_kor_isnm`). Failed enrichments end up in `errors` — the
        frontend still knows which rows exist and can render a degraded
        skeleton for each. An empty watchlist returns empty lists on both
        sides without any KIS traffic.
        """
        result = await self._session.execute(select(Watchlist).order_by(Watchlist.sort_order.asc(), Watchlist.id.asc()))
        entries = list(result.scalars().all())
        if not entries:
            return WatchlistEnrichmentResult(items=[], errors=[])

        # Fan out price lookups in parallel. One failure must not take
        # down the healthy siblings.
        price_results = await asyncio.gather(
            *(self._kis.inquire_stock_price(entry.symbol) for entry in entries),
            return_exceptions=True,
        )

        items: list[WatchlistItemResponse] = []
        errors: list[WatchlistItemError] = []
        for entry, price_result in zip(entries, price_results, strict=True):
            if isinstance(price_result, StockPriceResponse):
                # Prefer the live KIS Korean name so delisted/renamed
                # symbols surface immediately without a DB migration.
                live_name = price_result.output.name or entry.name or entry.symbol
                items.append(
                    WatchlistItemResponse(
                        id=entry.id,
                        symbol=entry.symbol,
                        name=live_name,
                        price=to_int(price_result.output.price),
                        change=to_int(price_result.output.change),
                        change_rate=to_float(price_result.output.change_rate),
                        volume=to_int(price_result.output.volume),
                        sort_order=entry.sort_order,
                        created_at=entry.created_at,
                    )
                )
                continue

            error_code, message = _classify_enrichment_error(price_result)
            logger.warning(
                "watchlist enrichment failed",
                extra={
                    "id": entry.id,
                    "symbol": entry.symbol,
                    "error_code": error_code,
                },
            )
            errors.append(
                WatchlistItemError(
                    id=entry.id,
                    symbol=entry.symbol,
                    sort_order=entry.sort_order,
                    error_code=error_code,
                    message=message,
                )
            )
        return WatchlistEnrichmentResult(items=items, errors=errors)

    async def add_watchlist(self, symbol: str) -> WatchlistItemCreatedResponse:
        # Atomic count + uniqueness check within the request transaction.
        count = await self._session.scalar(select(func.count()).select_from(Watchlist)) or 0
        if count >= MAX_WATCHLIST_ITEMS:
            raise WatchlistFullError()

        duplicate = await self._session.scalar(select(Watchlist).where(Watchlist.symbol == symbol))
        if duplicate is not None:
            raise DuplicateSymbolError(symbol)

        # Validate the symbol by asking KIS for current price. Grab the
        # Korean name while we're here, but treat it as best-effort —
        # list_watchlist always re-fetches the live name at read time, so
        # a stale DB value never surfaces to clients.
        price_resp = await self._kis.inquire_stock_price(symbol)
        name = price_resp.output.name or symbol

        entry = Watchlist(symbol=symbol, name=name, sort_order=count)
        self._session.add(entry)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # Concurrent add races the unique index.
            raise DuplicateSymbolError(symbol) from exc
        await self._session.refresh(entry)

        return WatchlistItemCreatedResponse(
            id=entry.id,
            symbol=entry.symbol,
            name=entry.name,
            sort_order=entry.sort_order,
            created_at=entry.created_at,
        )

    async def delete_watchlist(self, item_id: int) -> None:
        entry = await self._session.get(Watchlist, item_id)
        if entry is None:
            raise WatchlistNotFoundError(item_id)
        await self._session.delete(entry)

    async def reorder_watchlist(self, order: list[WatchlistOrderItem]) -> int:
        if not order:
            return 0
        ids = [item.id for item in order]
        existing = await self._session.execute(select(Watchlist.id).where(Watchlist.id.in_(ids)))
        existing_ids = {row for (row,) in existing.all()}
        missing = [item_id for item_id in ids if item_id not in existing_ids]
        if missing:
            raise WatchlistNotFoundError(missing[0])

        updated = 0
        for item in order:
            result = await self._session.execute(
                update(Watchlist).where(Watchlist.id == item.id).values(sort_order=item.sort_order)
            )
            updated += result.rowcount or 0
        return updated


def _classify_enrichment_error(exc: BaseException) -> tuple[str, str]:
    """Translate an enrichment exception into a (code, message) tuple."""
    if isinstance(exc, StockquareError):
        return exc.code, exc.message
    return "UNKNOWN_ERROR", type(exc).__name__
