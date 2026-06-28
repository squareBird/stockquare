"""Custom exception hierarchy for Stockquare backend."""

from __future__ import annotations

from typing import ClassVar


class StockquareError(Exception):
    """Base exception for all Stockquare business errors."""

    code: ClassVar[str] = "STOCKQUARE_ERROR"
    http_status: ClassVar[int] = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigError(StockquareError):
    """Missing or invalid configuration."""

    code: ClassVar[str] = "CONFIG_ERROR"
    http_status: ClassVar[int] = 500


class KISAPIError(StockquareError):
    """KIS Open API call failure."""

    code: ClassVar[str] = "KIS_API_ERROR"
    http_status: ClassVar[int] = 502

    def __init__(self, message: str = "Upstream KIS request failed") -> None:
        super().__init__(message)


class KISNotConfiguredError(StockquareError):
    """KIS credentials are missing — call fails before hitting the network.

    Returned to callers as HTTP 503 so the frontend can distinguish this
    "not deployable yet" state from a real upstream KIS outage.
    """

    code: ClassVar[str] = "KIS_NOT_CONFIGURED"
    http_status: ClassVar[int] = 503

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        joined = ", ".join(missing) if missing else "KIS credentials"
        super().__init__(f"KIS not configured (missing: {joined})")


class TokenExpiredError(KISAPIError):
    """KIS access token expired or refresh failed."""

    code: ClassVar[str] = "TOKEN_EXPIRED"
    http_status: ClassVar[int] = 401

    def __init__(self) -> None:
        super().__init__("Access token expired")


class InvalidSymbolError(StockquareError):
    """Stock symbol does not exist."""

    code: ClassVar[str] = "INVALID_SYMBOL"
    http_status: ClassVar[int] = 400

    def __init__(self, symbol: str) -> None:
        super().__init__(f"Invalid symbol: {symbol}")


class DuplicateSymbolError(StockquareError):
    """Symbol already present in watchlist."""

    code: ClassVar[str] = "DUPLICATE_SYMBOL"
    http_status: ClassVar[int] = 409

    def __init__(self, symbol: str) -> None:
        super().__init__(f"Symbol already in watchlist: {symbol}")


class WatchlistFullError(StockquareError):
    """Watchlist item limit reached."""

    code: ClassVar[str] = "WATCHLIST_FULL"
    http_status: ClassVar[int] = 400

    def __init__(self) -> None:
        super().__init__("Watchlist is full (max 20)")


class WatchlistNotFoundError(StockquareError):
    """Watchlist item not found."""

    code: ClassVar[str] = "NOT_FOUND"
    http_status: ClassVar[int] = 404

    def __init__(self, item_id: int) -> None:
        super().__init__(f"Watchlist item not found: {item_id}")


class InvalidQueryError(StockquareError):
    """Invalid stock search query."""

    code: ClassVar[str] = "INVALID_QUERY"
    http_status: ClassVar[int] = 400

    def __init__(self) -> None:
        super().__init__("Search query must not be empty")


# ---------------------------------------------------------------------------
# Trading — Phase 2 safety gates and KIS error surfaces
# ---------------------------------------------------------------------------


class TradingDisabledError(StockquareError):
    """Order placement blocked by `TRADING_REAL_MODE_ENABLED=false`.

    Raised when the deployment is running in real mode but the operator
    has explicitly disabled order mutations. Read-only KIS endpoints stay
    functional.
    """

    code: ClassVar[str] = "TRADING_DISABLED"
    http_status: ClassVar[int] = 403

    def __init__(self) -> None:
        super().__init__("Trading is disabled on this deployment")


class OrderAmountExceededError(StockquareError):
    """Order's total KRW value exceeds `TRADING_MAX_ORDER_AMOUNT`."""

    code: ClassVar[str] = "ORDER_AMOUNT_EXCEEDED"
    http_status: ClassVar[int] = 400

    def __init__(self, amount: int, limit: int) -> None:
        self.amount = amount
        self.limit = limit
        super().__init__(f"Order amount {amount} KRW exceeds the configured cap {limit} KRW")


class OrderNotFoundError(StockquareError):
    """Order id not found in KIS (likely already filled / cancelled)."""

    code: ClassVar[str] = "ORDER_NOT_FOUND"
    http_status: ClassVar[int] = 404

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order not found: {order_id}")


class OrderFailedError(StockquareError):
    """KIS rejected the order (insufficient balance, price limit, etc).

    Carries the KIS `msg_cd`/`msg1` so the frontend can surface the
    actionable rejection reason to the user without the backend having
    to translate the entire KIS error dictionary.
    """

    code: ClassVar[str] = "ORDER_FAILED"
    http_status: ClassVar[int] = 400

    def __init__(self, message: str, kis_msg_cd: str | None = None) -> None:
        self.kis_msg_cd = kis_msg_cd
        super().__init__(message)


# ---------------------------------------------------------------------------
# Strategy engine — Phase 1
# ---------------------------------------------------------------------------


class StrategyNotFoundError(StockquareError):
    """Strategy id not found."""

    code: ClassVar[str] = "STRATEGY_NOT_FOUND"
    http_status: ClassVar[int] = 404

    def __init__(self, strategy_id: int) -> None:
        super().__init__(f"Strategy not found: {strategy_id}")


# ---------------------------------------------------------------------------
# Assistant — Claude Agent SDK orchestration (ASSISTANT.md)
# ---------------------------------------------------------------------------


class AssistantNotConfiguredError(StockquareError):
    """Assistant disabled or local Claude Code is unavailable.

    Mirrors KISNotConfiguredError's "not deployable yet" 503: the assistant
    runs the user's local Claude Code through the Claude Agent SDK, so this is
    raised when the feature is disabled or the `claude` CLI is missing / not
    logged in. The rest of the app stays functional.
    """

    code: ClassVar[str] = "ASSISTANT_NOT_CONFIGURED"
    http_status: ClassVar[int] = 503

    def __init__(self, message: str = "AI assistant is not available") -> None:
        super().__init__(message)


class AssistantAPIError(StockquareError):
    """The Claude Agent SDK / local Claude Code failed during a chat turn."""

    code: ClassVar[str] = "ASSISTANT_API_ERROR"
    http_status: ClassVar[int] = 502

    def __init__(self, message: str = "AI assistant request failed") -> None:
        super().__init__(message)


class InvalidActionError(StockquareError):
    """A confirm request named a non-mutate or unknown tool."""

    code: ClassVar[str] = "INVALID_ACTION"
    http_status: ClassVar[int] = 400

    def __init__(self, tool: str) -> None:
        super().__init__(f"Action cannot be confirmed: {tool}")
