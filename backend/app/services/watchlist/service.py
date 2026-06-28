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
from app.services.stock_index import StockMasterIndex

logger = logging.getLogger(__name__)

MAX_WATCHLIST_ITEMS = 20


@dataclass
class WatchlistEnrichmentResult:
    """Bundle of enriched successes + per-item errors for a list call."""

    items: list[WatchlistItemResponse]
    errors: list[WatchlistItemError]


class WatchlistService:
    """Business logic for watchlist CRUD and enrichment."""

    def __init__(self, session: AsyncSession, kis: KISClient, index: StockMasterIndex) -> None:
        self._session = session
        self._kis = kis
        self._index = index

    def _resolve_name(self, symbol: str, fallback: str = "") -> str:
        """Resolve a display name for a symbol.

        KIS `inquire-price` (FHKST01010100) does NOT return the stock's
        Korean name — its `output` carries the market name
        (`rprs_mrkt_kor_name`) and sector name (`bstp_kor_isnm`) but no
        `hts_kor_isnm`. The authoritative Korean/English name comes from the
        in-memory master index instead. Falls back to the stored name, then
        the symbol, when the index has no row (e.g. a freshly listed code
        not yet in the snapshot).
        """
        row = self._index.by_symbol(symbol)
        if row is not None:
            name = row.name_ko or row.name_en
            if name:
                return name
        return fallback or symbol

    async def list_watchlist(self) -> WatchlistEnrichmentResult:
        """Return watchlist items enriched with live KIS price data.

        Successful KIS enrichments end up in `items` with the master-index
        Korean name. Failed enrichments end up in `errors` — the frontend
        still knows which rows exist and can render a degraded skeleton for
        each. An empty watchlist returns empty lists on both sides without
        any KIS traffic.
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
                # inquire-price has no stock name field; resolve it from the
                # master index, falling back to the stored name / symbol.
                live_name = self._resolve_name(entry.symbol, entry.name)
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

        # Validate the symbol by asking KIS for current price (raises
        # InvalidSymbolError on an unknown code). The name comes from the
        # master index, not inquire-price, which carries no stock name —
        # best-effort, since list_watchlist re-resolves it at read time.
        await self._kis.inquire_stock_price(symbol)
        name = self._resolve_name(symbol)

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

    async def delete_watchlist_by_symbol(self, symbol: str) -> None:
        """Remove a watchlist entry by its 6-digit symbol.

        The assistant only knows symbols (not DB ids), so the AI-driven remove
        path resolves the row by symbol. Raises WatchlistNotFoundError when no
        entry holds that symbol.
        """
        entry = await self._session.scalar(select(Watchlist).where(Watchlist.symbol == symbol))
        if entry is None:
            raise WatchlistNotFoundError(symbol)
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
