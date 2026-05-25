"""Trading domain models (Pydantic)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.core.config import AccountMode


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class CreateOrderRequest(BaseModel):
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(ge=1)
    price: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _require_price_for_limit_orders(self) -> CreateOrderRequest:
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit orders require a `price` field")
        return self


class ModifyOrderRequest(BaseModel):
    quantity: int = Field(ge=1)
    price: int = Field(ge=1)


class ModifyOrderResponse(BaseModel):
    """Narrow response for a successful modify.

    KIS `order-rvsecncl` does not echo the original symbol/side/order_type,
    so the response deliberately omits those fields rather than leaking
    fabricated defaults. The frontend should refetch `GET /orders` to
    render the updated row in full.
    """

    order_id: str
    quantity: int
    price: int
    submitted_at: datetime | None
    account_mode: AccountMode


class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    name: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: int | None
    filled_quantity: int = 0
    status: OrderStatus
    submitted_at: datetime | None = None
    account_mode: AccountMode


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    count: int


class CancelOrderResponse(BaseModel):
    order_id: str
    cancelled: bool
