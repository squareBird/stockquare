# Error Handling Pattern

Error handling patterns for FastAPI + KIS API integration.

## Custom Exception Hierarchy

Define business-level exceptions with class-level `code` + `http_status`
so the FastAPI exception handler can dispatch without an isinstance ladder.

```python
from typing import ClassVar


class StockquareError(Exception):
    """Base exception — all business errors inherit from this."""

    code: ClassVar[str] = "STOCKQUARE_ERROR"
    http_status: ClassVar[int] = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class KISAPIError(StockquareError):
    """KIS Open API call failure (upstream 4xx/5xx or network)."""

    code: ClassVar[str] = "KIS_API_ERROR"
    http_status: ClassVar[int] = 502

    def __init__(self, message: str = "Upstream KIS request failed") -> None:
        super().__init__(message)


class TokenExpiredError(KISAPIError):
    """KIS access token expired or refresh exhausted."""

    code: ClassVar[str] = "TOKEN_EXPIRED"
    http_status: ClassVar[int] = 401

    def __init__(self) -> None:
        super().__init__("Access token expired")


class KISNotConfiguredError(StockquareError):
    """KIS credentials missing — raised at request time, no network I/O.

    Preferred over startup crash so DB-only endpoints stay serviceable
    while KIS-dependent routes return 503 until operators fill the env.
    """

    code: ClassVar[str] = "KIS_NOT_CONFIGURED"
    http_status: ClassVar[int] = 503

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        joined = ", ".join(missing) if missing else "KIS credentials"
        super().__init__(f"KIS not configured (missing: {joined})")


# Domain-specific subclasses follow the same ClassVar pattern. Examples:
# InvalidSymbolError (400 / INVALID_SYMBOL), DuplicateSymbolError (409 /
# DUPLICATE_SYMBOL), WatchlistFullError (400 / WATCHLIST_FULL),
# WatchlistNotFoundError (404 / NOT_FOUND), InvalidQueryError (400 /
# INVALID_QUERY). Each lives in `app/core/exceptions.py`.
```

Two rules that fall out of this shape:

1. **One source of truth per error.** `http_status` lives on the class
   next to `code` — the handler never needs a parallel lookup table.
2. **Subclasses never re-define the base fields implicitly.** A subclass
   that needs a different HTTP status re-declares `http_status` as a new
   `ClassVar`; one that only changes the message signature overrides
   `__init__` without touching the classvars.

## FastAPI Exception Handler

Return all exceptions in a consistent JSON format. Use the subclass's
class-level `http_status` so adding a new exception never requires a
handler edit.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(StockquareError)
async def stockquare_error_handler(request: Request, exc: StockquareError) -> JSONResponse:
    logger.info(
        "stockquare error",
        extra={"code": exc.code, "path": request.url.path, "status": exc.http_status},
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message},
    )
```

## Error Response Format

```json
{
  "code": "KIS_API_ERROR",
  "message": "Failed to fetch stock price"
}
```

## Retry with Backoff

Retry transient/network errors with exponential backoff.

```python
import asyncio
from collections.abc import Callable, Awaitable
from typing import TypeVar

T = TypeVar("T")

async def with_retry(
    fn: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    for attempt in range(max_retries):
        try:
            return await fn(*args)
        except KISAPIError as e:
            if e.status_code < 500 or attempt == max_retries - 1:
                raise
            await asyncio.sleep(base_delay * (2 ** attempt))
    raise KISAPIError("Max retries exceeded", status_code=500)
```

## Logging

Use structured logging on errors. Never log sensitive data (tokens, secrets).

```python
import logging

logger = logging.getLogger(__name__)

async def place_order(order: OrderRequest) -> OrderResponse:
    try:
        result = await kis_client.create_order(order)
        logger.info("Order placed", extra={"symbol": order.symbol, "qty": order.quantity})
        return result
    except KISAPIError as e:
        logger.error("Order failed", extra={"symbol": order.symbol, "error": e.message})
        raise OrderFailedError(e.message)
```
