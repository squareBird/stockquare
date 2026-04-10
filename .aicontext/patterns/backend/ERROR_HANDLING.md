# Error Handling Pattern

Error handling patterns for FastAPI + KIS API integration.

## Custom Exception Hierarchy

Define business-level exceptions. Return consistent responses via FastAPI exception handlers.

```python
class StockquareError(Exception):
    """Base exception."""

    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code


class KISAPIError(StockquareError):
    """KIS API call failure."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message, code="KIS_API_ERROR")
        self.status_code = status_code


class TokenExpiredError(KISAPIError):
    """Access token expired."""

    def __init__(self) -> None:
        super().__init__("Access token expired", status_code=401)


class OrderFailedError(StockquareError):
    """Order execution failure."""

    def __init__(self, message: str, order_id: str | None = None) -> None:
        super().__init__(message, code="ORDER_FAILED")
        self.order_id = order_id


class InsufficientBalanceError(StockquareError):
    """Insufficient balance."""

    def __init__(self) -> None:
        super().__init__("Insufficient balance", code="INSUFFICIENT_BALANCE")
```

## FastAPI Exception Handler

Return all exceptions in a consistent JSON format.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(StockquareError)
async def stockquare_error_handler(request: Request, exc: StockquareError) -> JSONResponse:
    status_code = 400
    if isinstance(exc, KISAPIError):
        status_code = exc.status_code
    return JSONResponse(
        status_code=status_code,
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
