"""Strategy endpoints — CRUD + manual dry-run evaluation (Phase 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_kis_client, get_stock_index
from app.kis.client import KISClient
from app.models.strategy import (
    SignalResponse,
    SignalsResponse,
    StrategiesResponse,
    StrategyCreateRequest,
    StrategyResponse,
    StrategyUpdateRequest,
)
from app.services.stock_index import StockMasterIndex
from app.services.stocks import StocksService
from app.services.strategy import StrategyService

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _get_service(
    session: AsyncSession = Depends(get_db_session),
    kis: KISClient = Depends(get_kis_client),
    index: StockMasterIndex = Depends(get_stock_index),
) -> StrategyService:
    stocks = StocksService(kis=kis, index=index)
    return StrategyService(session=session, stocks=stocks, index=index)


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    payload: StrategyCreateRequest,
    service: StrategyService = Depends(_get_service),
) -> StrategyResponse:
    return await service.create_strategy(payload)


@router.get("", response_model=StrategiesResponse)
async def list_strategies(
    service: StrategyService = Depends(_get_service),
) -> StrategiesResponse:
    strategies = await service.list_strategies()
    return StrategiesResponse(strategies=strategies, count=len(strategies))


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    service: StrategyService = Depends(_get_service),
) -> StrategyResponse:
    return await service.get_strategy(strategy_id)


@router.patch("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    payload: StrategyUpdateRequest,
    service: StrategyService = Depends(_get_service),
) -> StrategyResponse:
    return await service.update_strategy(strategy_id, payload)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: int,
    service: StrategyService = Depends(_get_service),
) -> None:
    await service.delete_strategy(strategy_id)


@router.post("/{strategy_id}/evaluate", response_model=SignalResponse)
async def evaluate_strategy(
    strategy_id: int,
    service: StrategyService = Depends(_get_service),
) -> SignalResponse:
    """Evaluate now and return the signal. Never places an order (dry-run)."""
    return await service.evaluate(strategy_id)


@router.get("/{strategy_id}/signals", response_model=SignalsResponse)
async def list_signals(
    strategy_id: int,
    service: StrategyService = Depends(_get_service),
) -> SignalsResponse:
    signals = await service.list_signals(strategy_id)
    return SignalsResponse(signals=signals, count=len(signals))
