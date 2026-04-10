# API Integration Pattern

Patterns for integrating with the KIS Open API.

> Reference: https://apiportal.koreainvestment.com/intro

## HTTP Client

Use `httpx.AsyncClient` for async requests with session reuse.

```python
from httpx import AsyncClient

class KISClient:
    def __init__(self, config: KISConfig) -> None:
        self._client = AsyncClient(
            base_url=config.base_url,
            timeout=10.0,
        )
        self._config = config
        self._access_token: str | None = None

    async def close(self) -> None:
        await self._client.aclose()
```

## Token Management

Reuse OAuth 2.0 access tokens until expiry. Auto-refresh before expiration.

```python
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self, client: KISClient) -> None:
        self._client = client
        self._token: str | None = None
        self._expires_at: datetime | None = None

    async def get_token(self) -> str:
        if self._is_expired():
            await self._refresh()
        return self._token

    def _is_expired(self) -> bool:
        if self._token is None or self._expires_at is None:
            return True
        return datetime.now() >= self._expires_at - timedelta(minutes=5)
```

## API Request Wrapper

All KIS API calls go through a common wrapper that injects auth headers and parses responses.

```python
from typing import TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

async def request(
    self,
    method: str,
    path: str,
    tr_id: str,
    *,
    body: dict | None = None,
    response_model: type[T],
) -> T:
    token = await self._token_manager.get_token()
    headers = {
        "authorization": f"Bearer {token}",
        "appkey": self._config.app_key,
        "appsecret": self._config.app_secret,
        "tr_id": tr_id,
    }
    response = await self._client.request(
        method, path, headers=headers, json=body,
    )
    response.raise_for_status()
    return response_model.model_validate(response.json())
```

## Response Models

Validate KIS API responses with Pydantic models. Map original field names via aliases.

```python
from pydantic import BaseModel, Field

class StockPrice(BaseModel):
    symbol: str = Field(alias="stck_shrn_iscd")
    price: int = Field(alias="stck_prpr")
    change: int = Field(alias="prdy_vrss")
    change_rate: float = Field(alias="prdy_ctrt")
    volume: int = Field(alias="acml_vol")

    model_config = {"populate_by_name": True}
```

## Rate Limiting

KIS API enforces per-second call limits. Control request intervals.

```python
import asyncio

class RateLimiter:
    def __init__(self, calls_per_second: int = 20) -> None:
        self._semaphore = asyncio.Semaphore(calls_per_second)
        self._interval = 1.0 / calls_per_second

    async def acquire(self) -> None:
        await self._semaphore.acquire()
        asyncio.get_event_loop().call_later(self._interval, self._semaphore.release)
```
