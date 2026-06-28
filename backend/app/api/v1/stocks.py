"""Stocks endpoints — symbol search."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import get_kis_client, get_stock_index
from app.kis.client import KISClient
from app.models.stocks import (
    ChartInterval,
    StockHistoryResponse,
    StockMarket,
    StockSearchItemResponse,
    StockSearchResponse,
)
from app.services.stock_index import StockMasterIndex
from app.services.stocks import StocksService

router = APIRouter(prefix="/stocks", tags=["stocks"])


def _get_service(
    kis: KISClient = Depends(get_kis_client),
    index: StockMasterIndex = Depends(get_stock_index),
) -> StocksService:
    return StocksService(kis=kis, index=index)


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


@router.get("/{symbol}/history", response_model=StockHistoryResponse)
async def stock_history(
    symbol: Annotated[str, Path(pattern=r"^\d{6}$", description="6-digit KRX code")],
    interval: Annotated[
        ChartInterval, Query(description="Candle granularity")
    ] = ChartInterval.DAY,
    service: StocksService = Depends(_get_service),
) -> StockHistoryResponse:
    candles = await service.get_history(symbol, interval)
    return StockHistoryResponse(symbol=symbol, interval=interval, candles=candles)
