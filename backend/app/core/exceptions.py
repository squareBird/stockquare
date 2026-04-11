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
