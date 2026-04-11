"""Stocks endpoints — symbol search."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_kis_client
from app.kis.client import KISClient
from app.models.stocks import (
    StockMarket,
    StockSearchItemResponse,
    StockSearchResponse,
)
from app.services.stocks import StocksService

router = APIRouter(prefix="/stocks", tags=["stocks"])


def _get_service(kis: KISClient = Depends(get_kis_client)) -> StocksService:
    return StocksService(kis=kis)


@router.get("/search", response_model=StockSearchResponse)
async def stock_search(
    q: Annotated[str, Query(min_length=1, description="Symbol or name")],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    service: StocksService = Depends(_get_service),
) -> StockSearchResponse:
    results = await service.search_stocks(q, limit)
    items = [
        StockSearchItemResponse(
            symbol=item.symbol,
            name=item.name,
            market=StockMarket(item.market),
        )
        for item in results
    ]
    return StockSearchResponse(items=items, count=len(items))
