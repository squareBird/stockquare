"""Market business logic — indices with KST trading-session status."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from app.core.exceptions import StockquareError
from app.kis.client import KISClient
from app.kis.models import IndexResponse, MarketStatus
from app.services._helpers import to_float, to_int

logger = logging.getLogger(__name__)

# Korean Standard Time is UTC+9, no DST.
_KST_OFFSET = timedelta(hours=9)

_INDEX_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("0001", "KOSPI"),
    ("1001", "KOSDAQ"),
)


@dataclass
class MarketIndex:
    code: str
    name: str
    value: float
    change: float
    change_rate: float
    volume: int
    status: MarketStatus


@dataclass
class MarketIndexError:
    code: str
    name: str
    error_code: str
    message: str


@dataclass
class MarketIndicesResult:
    """Partial-failure-safe bundle: successes and per-index errors."""

    indices: list[MarketIndex]
    errors: list[MarketIndexError]


def _current_market_status(now_utc: datetime | None = None) -> MarketStatus:
    """Compute the KRX market status from a KST wall clock.

    KRX regular session: 09:00–15:30 KST (Mon–Fri).
    Pre-market 08:00–09:00, post-market 15:30–18:00.
    """
    now_utc = now_utc or datetime.now(UTC)
    kst = now_utc + _KST_OFFSET
    if kst.weekday() >= 5:
        return MarketStatus.CLOSED
    clock = kst.time()
    if time(9, 0) <= clock < time(15, 30):
        return MarketStatus.OPEN
    if time(8, 0) <= clock < time(9, 0):
        return MarketStatus.PRE_MARKET
    if time(15, 30) <= clock < time(18, 0):
        return MarketStatus.POST_MARKET
    return MarketStatus.CLOSED


class MarketService:
    """Business logic for market-wide endpoints."""

    def __init__(self, kis: KISClient) -> None:
        self._kis = kis

    async def get_market_indices(self) -> MarketIndicesResult:
        """Fetch KOSPI and KOSDAQ in parallel with graceful partial failure.

        KIS occasionally returns HTTP 500 for `inquire-index-price` on
        individual index codes while the sibling code succeeds. Using
        `asyncio.gather(..., return_exceptions=True)` lets us surface the
        healthy index to the caller instead of forcing a 502 on the whole
        endpoint. The caller receives an `errors[]` list for the failed
        slots so the frontend can render a degraded skeleton for just that
        card.
        """
        raw_results = await asyncio.gather(
            *(self._kis.inquire_index(code) for code, _ in _INDEX_DEFINITIONS),
            return_exceptions=True,
        )
        status = _current_market_status()
        indices: list[MarketIndex] = []
        errors: list[MarketIndexError] = []
        for (code, name), result in zip(_INDEX_DEFINITIONS, raw_results, strict=True):
            if isinstance(result, IndexResponse):
                indices.append(
                    MarketIndex(
                        code=code,
                        name=name,
                        value=to_float(result.output.value),
                        change=to_float(result.output.change),
                        change_rate=to_float(result.output.change_rate),
                        volume=to_int(result.output.volume),
                        status=status,
                    )
                )
                continue
            # A failure — capture the slot as an error and keep serving the rest.
            error_code, message = _classify_index_error(result)
            logger.warning(
                "market index fetch failed",
                extra={
                    "index_code": code,
                    "index_name": name,
                    "error_code": error_code,
                },
            )
            errors.append(
                MarketIndexError(
                    code=code,
                    name=name,
                    error_code=error_code,
                    message=message,
                )
            )
        return MarketIndicesResult(indices=indices, errors=errors)


def _classify_index_error(exc: BaseException) -> tuple[str, str]:
    """Translate an exception into a (code, message) tuple for the client."""
    if isinstance(exc, StockquareError):
        return exc.code, exc.message
    return "UNKNOWN_ERROR", type(exc).__name__
