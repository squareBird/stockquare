# Realtime Data Pattern

Patterns for receiving real-time market data via KIS WebSocket.

## WebSocket Connection

KIS provides real-time quotes over WebSocket. Handle connection management and auto-reconnect.

```python
import asyncio
import json

import websockets
from websockets.asyncio.client import ClientConnection

class KISWebSocket:
    def __init__(self, config: KISConfig) -> None:
        self._config = config
        self._ws: ClientConnection | None = None
        self._subscriptions: set[str] = set()
        self._running = False

    async def connect(self) -> None:
        self._running = True
        while self._running:
            try:
                async with websockets.connect(self._config.ws_url) as ws:
                    self._ws = ws
                    await self._resubscribe()
                    await self._listen(ws)
            except websockets.ConnectionClosed:
                await asyncio.sleep(3.0)

    async def disconnect(self) -> None:
        self._running = False
        if self._ws:
            await self._ws.close()
```

## Subscription Management

Subscribe/unsubscribe to real-time quotes per symbol.

```python
async def subscribe(self, symbol: str) -> None:
    self._subscriptions.add(symbol)
    if self._ws:
        message = {
            "header": {"tr_type": "1", "approval_key": self._config.approval_key},
            "body": {"tr_id": "H0STCNT0", "tr_key": symbol},
        }
        await self._ws.send(json.dumps(message))

async def unsubscribe(self, symbol: str) -> None:
    self._subscriptions.discard(symbol)
    if self._ws:
        message = {
            "header": {"tr_type": "2", "approval_key": self._config.approval_key},
            "body": {"tr_id": "H0STCNT0", "tr_key": symbol},
        }
        await self._ws.send(json.dumps(message))

async def _resubscribe(self) -> None:
    for symbol in self._subscriptions:
        await self.subscribe(symbol)
```

## Message Handling

Parse incoming data and dispatch to registered handlers.

```python
from collections.abc import Callable, Awaitable

class KISWebSocket:
    def __init__(self, config: KISConfig) -> None:
        ...
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable[..., Awaitable]) -> None:
        self._handlers.setdefault(event, []).append(handler)

    async def _listen(self, ws: ClientConnection) -> None:
        async for raw in ws:
            data = self._parse(raw)
            if data and data.tr_id in self._handlers:
                for handler in self._handlers[data.tr_id]:
                    await handler(data)
```

## Relay to Frontend

Forward data to frontend clients via FastAPI WebSocket endpoint.

```python
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, symbol: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(symbol, []).append(ws)

    async def broadcast(self, symbol: str, data: dict) -> None:
        for ws in self._connections.get(symbol, []):
            await ws.send_json(data)
```

## Data Flow

```
KIS WebSocket → KISWebSocket (receive/parse) → ConnectionManager (relay) → Frontend WebSocket
```
