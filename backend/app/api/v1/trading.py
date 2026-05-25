"""Trading endpoints — order CRUD backed by KIS order-cash."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Path, status

from app.api.deps import get_kis_client
from app.core.config import Settings, get_settings
from app.kis.client import KISClient
from app.models.trading import (
    CancelOrderResponse,
    CreateOrderRequest,
    ModifyOrderRequest,
    ModifyOrderResponse,
    OrderListResponse,
    OrderResponse,
)
from app.services.trading import TradingService

router = APIRouter(prefix="/orders", tags=["trading"])

_KST = ZoneInfo("Asia/Seoul")

# Path parameter pattern for `order_id` — accepts either a bare 1-10 digit
# ODNO or the composite `{1-5 digit branch}-{1-10 digit odno}`. Anything
# else (control chars, letters, slashes) is rejected by FastAPI before
# the handler runs, closing the order-id injection vector flagged in the
# Phase 2 security review.
_ORDER_ID_PATTERN = r"^(?:\d{1,5}-)?\d{1,10}$"
OrderIdPath = Annotated[str, Path(pattern=_ORDER_ID_PATTERN, description="Order id")]


def _get_service(
    kis: KISClient = Depends(get_kis_client),
    settings: Settings = Depends(get_settings),
) -> TradingService:
    return TradingService(kis=kis, settings=settings)


def _default_date_window() -> tuple[str, str]:
    """Return a (from, to) YYYYMMDD pair covering the last 7 days in KST.

    KIS `INQR_STRT_DT / INQR_END_DT` are KST calendar dates; computing
    the window in UTC loses the last 9 hours of submissions every
    midnight-KST rollover.
    """
    today = datetime.now(_KST).date()
    return (today - timedelta(days=7)).strftime("%Y%m%d"), today.strftime("%Y%m%d")


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CreateOrderRequest,
    service: TradingService = Depends(_get_service),
) -> OrderResponse:
    return await service.create_order(payload)


@router.get("", response_model=OrderListResponse)
async def list_orders(
    service: TradingService = Depends(_get_service),
) -> OrderListResponse:
    from_date, to_date = _default_date_window()
    orders = await service.list_orders(from_date=from_date, to_date=to_date)
    return OrderListResponse(orders=orders, count=len(orders))


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: OrderIdPath,
    service: TradingService = Depends(_get_service),
) -> OrderResponse:
    from_date, to_date = _default_date_window()
    return await service.get_order(order_id, from_date=from_date, to_date=to_date)


@router.delete("/{order_id}", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: OrderIdPath,
    service: TradingService = Depends(_get_service),
) -> CancelOrderResponse:
    await service.cancel_order(order_id)
    return CancelOrderResponse(order_id=order_id, cancelled=True)


@router.patch("/{order_id}", response_model=ModifyOrderResponse)
async def modify_order(
    order_id: OrderIdPath,
    payload: ModifyOrderRequest,
    service: TradingService = Depends(_get_service),
) -> ModifyOrderResponse:
    result = await service.modify_order(
        order_id,
        quantity=payload.quantity,
        price=payload.price,
    )
    return ModifyOrderResponse(**result)  # type: ignore[arg-type]
