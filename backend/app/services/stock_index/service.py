"""In-memory stock listing index with ranked fuzzy search.

The index is built from the KIS master files on application startup.
Search is tier-based: exact symbol > exact name > prefix > substring,
case-insensitive and NFC-normalized. Rows are served entirely from
memory — no DB, no network — so search latency stays in the low
single-digit milliseconds even on a cold cache.

On-disk cache (``cache_dir/{market}.jsonl``) keeps a parsed snapshot
across restarts with a 24-hour TTL so the next process boot doesn't
need to re-download the CDN zips.
"""

from __future__ import annotations

import asyncio
import json
import logging
import unicodedata
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import time

import httpx

from app.kis.master import (
    StockMasterRow,
    download_amex,
    download_kosdaq,
    download_kospi,
    download_nasdaq,
    download_nyse,
)
from app.models.stocks import StockMarket

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 24 * 60 * 60

_MARKET_ORDER: dict[StockMarket, int] = {
    StockMarket.KOSPI: 0,
    StockMarket.KOSDAQ: 1,
    StockMarket.NASDAQ: 2,
    StockMarket.NYSE: 3,
    StockMarket.AMEX: 4,
}

# Tier constants used by StockMasterIndex.search. Lower = better match.
_TIER_EXACT_SYMBOL = 0
_TIER_EXACT_NAME = 1
_TIER_PREFIX = 2
_TIER_SUBSTRING = 3


def _normalize(value: str) -> str:
    """NFC-normalize and lowercase a string for case-insensitive compare."""
    return unicodedata.normalize("NFC", value).casefold()


class StockMasterIndex:
    """In-memory stock listing index with ranked search."""

    def __init__(self) -> None:
        self._rows: tuple[StockMasterRow, ...] = ()
        self._by_symbol: dict[str, StockMasterRow] = {}

    def __len__(self) -> int:
        return len(self._rows)

    def is_empty(self) -> bool:
        """Return True when the index has no rows."""
        return not self._rows

    def replace(self, rows: list[StockMasterRow]) -> None:
        """Atomically swap the backing rows.

        Called after a successful refresh. Both ``_rows`` and
        ``_by_symbol`` are rebuilt from scratch so readers never see
        a half-updated state — Python's GIL makes the tuple/dict
        assignments atomic from the point of view of search callers.
        """
        new_rows = tuple(rows)
        new_by_symbol = {row.symbol: row for row in new_rows}
        self._rows = new_rows
        self._by_symbol = new_by_symbol

    def by_symbol(self, symbol: str) -> StockMasterRow | None:
        """Return the row with the given symbol, or None."""
        return self._by_symbol.get(symbol)

    def search(self, query: str, limit: int) -> list[StockMasterRow]:
        """Return up to ``limit`` rows matching ``query``, best first.

        Ranking tiers (descending quality):
            0. Symbol exact match (upper-cased).
            1. Korean or English name exact match.
            2. Korean or English name prefix match.
            3. Korean or English name substring match.

        Within a tier, rows are ordered by market (KOSPI, KOSDAQ,
        NASDAQ, NYSE, AMEX) then by their position in the backing
        tuple for stability.

        Args:
            query: Raw user input. Empty string yields an empty list.
            limit: Maximum rows to return.

        Returns:
            List of up to ``limit`` rows, best match first.
        """
        if not query or limit <= 0 or not self._rows:
            return []

        query_upper = query.strip().upper()
        query_norm = _normalize(query)
        if not query_norm:
            return []

        scored: list[tuple[int, int, int, StockMasterRow]] = []
        for idx, row in enumerate(self._rows):
            tier = self._score_row(row, query_upper, query_norm)
            if tier is None:
                continue
            scored.append((tier, _MARKET_ORDER.get(row.market, 99), idx, row))

        scored.sort(key=lambda entry: (entry[0], entry[1], entry[2]))
        return [row for _, _, _, row in scored[:limit]]

    @staticmethod
    def _score_row(
        row: StockMasterRow,
        query_upper: str,
        query_norm: str,
    ) -> int | None:
        """Return the tier index for a row, or None if it doesn't match."""
        if row.symbol.upper() == query_upper:
            return _TIER_EXACT_SYMBOL

        name_ko_norm = _normalize(row.name_ko) if row.name_ko else ""
        name_en_norm = _normalize(row.name_en) if row.name_en else ""

        if not name_ko_norm and not name_en_norm:
            return None

        if name_ko_norm == query_norm or name_en_norm == query_norm:
            return _TIER_EXACT_NAME
        if name_ko_norm.startswith(query_norm) or name_en_norm.startswith(query_norm):
            return _TIER_PREFIX
        if query_norm in name_ko_norm or query_norm in name_en_norm:
            return _TIER_SUBSTRING
        return None


# ---------------------------------------------------------------------------
# Refresh + on-disk cache
# ---------------------------------------------------------------------------


_Downloader = Callable[[httpx.AsyncClient], Awaitable[list[StockMasterRow]]]

_DOWNLOADERS: dict[StockMarket, _Downloader] = {
    StockMarket.KOSPI: download_kospi,
    StockMarket.KOSDAQ: download_kosdaq,
    StockMarket.NASDAQ: download_nasdaq,
    StockMarket.NYSE: download_nyse,
    StockMarket.AMEX: download_amex,
}


def _cache_path(cache_dir: Path, market: StockMarket) -> Path:
    return cache_dir / f"{market.value}.jsonl"


def _load_cached_rows(path: Path, market: StockMarket) -> list[StockMasterRow] | None:
    """Return cached rows for a market if the snapshot is still fresh."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            header_line = fh.readline()
            if not header_line:
                return None
            header = json.loads(header_line)
            cached_at = float(header.get("cached_at", 0))
            if cached_at + _CACHE_TTL_SECONDS <= time():
                return None
            rows: list[StockMasterRow] = []
            for line in fh:
                if not line.strip():
                    continue
                data = json.loads(line)
                rows.append(
                    StockMasterRow(
                        symbol=data["symbol"],
                        name_ko=data["name_ko"],
                        name_en=data["name_en"],
                        market=market,
                    )
                )
            return rows
    except (OSError, ValueError, KeyError) as exc:
        logger.warning(
            "stock master cache load failed",
            extra={"market": market.value, "exc_type": type(exc).__name__},
        )
        return None


def _write_cached_rows(path: Path, rows: list[StockMasterRow]) -> None:
    """Persist a market snapshot to disk."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"cached_at": time()}) + "\n")
            for row in rows:
                fh.write(
                    json.dumps(
                        {
                            "symbol": row.symbol,
                            "name_ko": row.name_ko,
                            "name_en": row.name_en,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    except OSError as exc:
        logger.warning(
            "stock master cache write failed",
            extra={"path": str(path), "exc_type": type(exc).__name__},
        )


async def _fetch_market(
    http: httpx.AsyncClient,
    market: StockMarket,
    cache_dir: Path,
) -> tuple[StockMarket, list[StockMasterRow], bool]:
    """Return (market, rows, fresh) for a single market.

    ``fresh`` is True when the rows came from a live download (and thus
    should be written back to the cache). False means the rows were
    served from an existing on-disk snapshot.
    """
    path = _cache_path(cache_dir, market)
    cached = _load_cached_rows(path, market)
    if cached is not None:
        return market, cached, False
    downloader = _DOWNLOADERS[market]
    rows = await downloader(http)
    return market, rows, True


async def refresh_stock_master_index(
    http: httpx.AsyncClient,
    index: StockMasterIndex,
    cache_dir: Path,
) -> None:
    """Download + parse all five masters in parallel and swap into ``index``.

    Uses the on-disk cache at ``cache_dir/{market}.jsonl`` with a
    24-hour TTL. Per-market failures are logged and swallowed — a
    partial index is strictly better than no index. If every market
    fails and nothing is cached, the index stays empty and the caller
    will fall back to symbol-only search.

    Args:
        http: Shared httpx.AsyncClient for the master-file CDN. The
            caller owns its lifecycle.
        index: The :class:`StockMasterIndex` to update in place.
        cache_dir: Directory used for the on-disk snapshot cache.
            Created if missing.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    tasks = [_fetch_market(http, market, cache_dir) for market in _DOWNLOADERS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_rows: list[StockMasterRow] = []
    loaded_markets: list[str] = []
    for market, result in zip(_DOWNLOADERS.keys(), results, strict=True):
        if isinstance(result, BaseException):
            logger.warning(
                "stock master refresh failed for market",
                extra={"market": market.value, "exc_type": type(result).__name__},
            )
            continue
        _, rows, fresh = result
        all_rows.extend(rows)
        loaded_markets.append(market.value)
        if fresh:
            _write_cached_rows(_cache_path(cache_dir, market), rows)

    if not all_rows:
        logger.warning("stock master index refresh produced no rows")
        return

    index.replace(all_rows)
    logger.info(
        "stock master index refreshed",
        extra={"total_rows": len(all_rows), "markets": loaded_markets},
    )
