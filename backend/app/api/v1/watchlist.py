"""Watchlist endpoints — CRUD and reorder."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_kis_client
from app.kis.client import KISClient
from app.models.watchlist import (
    WatchlistAddRequest,
    WatchlistItemCreatedResponse,
    WatchlistReorderRequest,
    WatchlistReorderResponse,
    WatchlistResponse,
)
from app.services.watchlist import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _get_service(
    session: AsyncSession = Depends(get_db_session),
    kis: KISClient = Depends(get_kis_client),
) -> WatchlistService:
    return WatchlistService(session=session, kis=kis)


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(
    service: WatchlistService = Depends(_get_service),
) -> WatchlistResponse:
    result = await service.list_watchlist()
    return WatchlistResponse(
        items=result.items,
        errors=result.errors,
        count=len(result.items) + len(result.errors),
    )


@router.post(
    "",
    response_model=WatchlistItemCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_watchlist(
    payload: WatchlistAddRequest,
    service: WatchlistService = Depends(_get_service),
) -> WatchlistItemCreatedResponse:
    return await service.add_watchlist(payload.symbol)


@router.patch("/reorder", response_model=WatchlistReorderResponse)
async def reorder_watchlist(
    payload: WatchlistReorderRequest,
    service: WatchlistService = Depends(_get_service),
) -> WatchlistReorderResponse:
    updated = await service.reorder_watchlist(payload.order)
    return WatchlistReorderResponse(updated=updated)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    item_id: int,
    service: WatchlistService = Depends(_get_service),
) -> None:
    await service.delete_watchlist(item_id)
