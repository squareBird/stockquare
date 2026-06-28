"""Assistant endpoints — conversational chat + mutate confirmation.

Backend contract: `.aicontext/spec/backend/ASSISTANT.md`. The assistant runs
the user's local Claude Code through the Claude Agent SDK; these endpoints are
the thin HTTP surface over `AssistantService`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_kis_client, get_stock_index
from app.core.config import Settings, get_settings
from app.kis.client import KISClient
from app.models.assistant import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    ConfirmResponse,
)
from app.services.assistant import AssistantService
from app.services.portfolio import PortfolioHoldingsService, PortfolioService
from app.services.stock_index import StockMasterIndex
from app.services.stocks import StocksService
from app.services.watchlist import WatchlistService

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _get_service(
    session: AsyncSession = Depends(get_db_session),
    kis: KISClient = Depends(get_kis_client),
    index: StockMasterIndex = Depends(get_stock_index),
    settings: Settings = Depends(get_settings),
) -> AssistantService:
    stocks = StocksService(kis=kis, index=index)
    watchlist = WatchlistService(session=session, kis=kis, index=index)
    portfolio = PortfolioService(kis=kis)
    holdings = PortfolioHoldingsService(kis=kis)
    return AssistantService(
        settings=settings,
        stocks=stocks,
        watchlist=watchlist,
        portfolio=portfolio,
        holdings=holdings,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: AssistantService = Depends(_get_service),
) -> ChatResponse:
    return await service.chat(payload.messages)


async def _sse_events(service: AssistantService, messages: list[ChatMessage]) -> AsyncIterator[str]:
    """Serialize the service's chat-stream events as SSE `data:` lines.

    `chat_stream` validates availability before the first yield, so an
    unconfigured assistant raises here and is mapped to 503 by the exception
    handler before the response body opens.
    """
    async for event in service.chat_stream(messages):
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    service: AssistantService = Depends(_get_service),
) -> StreamingResponse:
    """Stream a chat turn as Server-Sent Events (text deltas + a final event).

    Mirrors `/chat` but emits tokens as the model produces them. The client
    accumulates `delta` events into the live reply, then applies the `final`
    event's structured extras (recommendations / pending actions). Falls back
    to `/chat` on the client when streaming is unavailable.
    """
    # Pre-flight before opening the SSE body so an unconfigured assistant maps
    # to a clean 503 (a raise mid-stream cannot set the response status).
    service.ensure_available()
    return StreamingResponse(
        _sse_events(service, payload.messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(
    payload: ConfirmRequest,
    service: AssistantService = Depends(_get_service),
) -> ConfirmResponse:
    return await service.confirm(payload.action)
