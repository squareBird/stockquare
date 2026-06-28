"""Assistant endpoints — conversational chat + mutate confirmation.

Backend contract: `.aicontext/spec/backend/ASSISTANT.md`. The assistant runs
the user's local Claude Code through the Claude Agent SDK; these endpoints are
the thin HTTP surface over `AssistantService`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_kis_client, get_stock_index
from app.core.config import Settings, get_settings
from app.kis.client import KISClient
from app.models.assistant import (
    ChatRequest,
    ChatResponse,
    ConfirmRequest,
    ConfirmResponse,
)
from app.services.assistant import AssistantService
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
    return AssistantService(settings=settings, stocks=stocks, watchlist=watchlist)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: AssistantService = Depends(_get_service),
) -> ChatResponse:
    return await service.chat(payload.messages)


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(
    payload: ConfirmRequest,
    service: AssistantService = Depends(_get_service),
) -> ConfirmResponse:
    return await service.confirm(payload.action)
