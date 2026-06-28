"""Trading business logic — order placement, modify, cancel, history.

This module holds every code path that can move real money. Safety gates:

1. `TRADING_REAL_MODE_ENABLED` (env var) — if `KIS_ACCOUNT_MODE=real` and
   this flag is false, every order mutation raises `TradingDisabledError`
   (HTTP 403) before touching KIS. Read-only endpoints are unaffected.
2. `TRADING_MAX_ORDER_AMOUNT` (env var, default 50,000 KRW) — the product
   of `quantity × price` is compared against this cap. Limit orders use
   the caller-supplied price. **Market orders fetch the last-traded price
   from KIS** (`inquire_stock_price`) and compute the notional against
   that — this closes the Phase 2 review finding where market orders
   skipped the cap entirely. Orders above the cap raise
   `OrderAmountExceededError` (HTTP 400) before touching KIS.
3. Every create/modify/cancel attempt is logged at WARNING level (real)
   or INFO (mock) with structured `extra={account_mode, symbol, side,
   quantity, price, amount}`. **Credentials are never logged** — only
   the business-level fields above.

Modify orders only support **limit** orders in Phase 2. KIS market orders
execute immediately on KRX and are effectively not modifiable. Callers
who attempt to modify a market order will receive the KIS-side rejection
verbatim via `OrderFailedError`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.config import AccountMode, Settings
from app.core.exceptions import (
    InvalidSymbolError,
    OrderAmountExceededError,
    OrderFailedError,
    OrderNotFoundError,
    TradingDisabledError,
)
from app.kis.client import KISClient
from app.kis.models import DailyCcldResponse, OrderCashResponse
from app.models.trading import (
    CreateOrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services._helpers import to_int

logger = logging.getLogger(__name__)

# Composite order id format: "{branch_office}-{odno}". Both halves are
# needed together for cancel/modify; encoding them in the public id keeps
# the API surface stateless (no server-side order cache).
_ORDER_ID_SEPARATOR = "-"

# Accepts either a bare 1-10 digit odno or a composite "{1-5}-{1-10}".
# Validated at parse time to block injection into the KIS request body.
_ORDER_ID_RE = re.compile(r"^(?:(\d{1,5})-)?(\d{1,10})$")

# KST zone for KIS timestamps. KIS always returns `HHMMSS` strings in KST
# and `INQR_STRT_DT / INQR_END_DT` date params are KST calendar dates.
_KST = ZoneInfo("Asia/Seoul")

# KIS side code mapping: "01" = sell, "02" = buy in the daily-ccld output.
_KIS_SIDE_TO_ENUM = {
    "01": OrderSide.SELL,
    "02": OrderSide.BUY,
}

# KIS ORD_DVSN_CD mapping on read-side (daily-ccld output).
_KIS_ORDER_TYPE_TO_ENUM = {
    "00": OrderType.LIMIT,
    "01": OrderType.MARKET,
}


@dataclass
class OrderExecution:
    """Internal representation of a KIS daily-ccld row."""

    order_id: str  # bare ODNO from KIS
    branch_office: str  # KRX_FWDG_ORD_ORGNO / ord_gno_brno
    composite_id: str  # `"{branch}-{odno}"` — client-facing id
    symbol: str
    name: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    filled_quantity: int
    price: int
    status: OrderStatus
    submitted_at: datetime | None


class TradingService:
    """Money-moving business logic. Every path goes through safety gates."""

    def __init__(self, kis: KISClient, settings: Settings) -> None:
        self._kis = kis
        self._settings = settings

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_order(self, payload: CreateOrderRequest) -> OrderResponse:
        self._enforce_real_mode_gate()
        # The amount cap for market orders requires a live price lookup,
        # so it is awaited here instead of running synchronously.
        await self._enforce_amount_cap(payload)

        price_for_kis = payload.price if payload.price is not None else 0
        self._log_order_attempt("create", payload, price_for_kis)

        response = await self._kis.order_cash(
            symbol=payload.symbol,
            side=payload.side.value,
            quantity=payload.quantity,
            price=price_for_kis,
            order_type=payload.order_type.value,
        )
        self._raise_if_kis_rejected(response)
        output = self._require_output(response)

        order_id = self._compose_order_id(
            output.krx_fwdg_ord_orgno,
            output.odno,
        )
        submitted_at = self._parse_kis_time(output.ord_tmd)

        return OrderResponse(
            order_id=order_id,
            symbol=payload.symbol,
            name=payload.symbol,  # fresh name lookup happens on list/get
            side=payload.side,
            order_type=payload.order_type,
            quantity=payload.quantity,
            price=payload.price,
            filled_quantity=0,
            status=OrderStatus.SUBMITTED,
            submitted_at=submitted_at,
            account_mode=self._settings.kis_account_mode,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def list_orders(self, *, from_date: str, to_date: str) -> list[OrderResponse]:
        response = await self._kis.inquire_daily_ccld(from_date=from_date, to_date=to_date)
        return [self._to_order_response(row) for row in self._executions_from(response)]

    async def get_order(self, order_id: str, *, from_date: str, to_date: str) -> OrderResponse:
        self._parse_order_id(order_id)  # validates the id shape
        response = await self._kis.inquire_daily_ccld(from_date=from_date, to_date=to_date)
        for row in self._executions_from(response):
            if row.composite_id == order_id or row.order_id == order_id:
                return self._to_order_response(row)
        raise OrderNotFoundError(order_id)

    # ------------------------------------------------------------------
    # Modify / Cancel
    # ------------------------------------------------------------------

    async def cancel_order(self, order_id: str) -> None:
        self._enforce_real_mode_gate()
        branch, odno = self._parse_order_id(order_id)
        self._log_order_mutation("cancel", order_id)
        response = await self._kis.order_revise_cancel(
            krx_fwdg_ord_orgno=branch,
            original_order_id=odno,
            operation="cancel",
        )
        self._raise_if_kis_rejected(response)

    async def modify_order(
        self,
        order_id: str,
        *,
        quantity: int,
        price: int,
    ) -> dict[str, object]:
        """Modify an existing limit order.

        Returns a narrow dict (not `OrderResponse`) because KIS does not
        echo symbol/side on the modify reply. Fabricating those fields
        would leak incorrect data to the client. The frontend should
        refetch `GET /orders` after a successful modify to render the
        updated row in full.
        """
        self._enforce_real_mode_gate()
        # Amount cap re-validation: a price-bump modify could push the
        # order above the configured cap.
        self._check_amount_cap_raw(quantity=quantity, price=price)
        branch, odno = self._parse_order_id(order_id)
        self._log_order_mutation("modify", order_id, quantity=quantity, price=price)

        response = await self._kis.order_revise_cancel(
            krx_fwdg_ord_orgno=branch,
            original_order_id=odno,
            operation="modify",
            quantity=quantity,
            price=price,
            order_type="limit",
        )
        self._raise_if_kis_rejected(response)
        output = self._require_output(response)

        new_order_id = self._compose_order_id(
            output.krx_fwdg_ord_orgno or branch,
            output.odno or odno,
        )
        return {
            "order_id": new_order_id,
            "quantity": quantity,
            "price": price,
            "submitted_at": self._parse_kis_time(output.ord_tmd),
            "account_mode": self._settings.kis_account_mode,
        }

    # ------------------------------------------------------------------
    # Safety gates
    # ------------------------------------------------------------------

    def _enforce_real_mode_gate(self) -> None:
        if self._settings.kis_account_mode == AccountMode.REAL and not self._settings.trading_real_mode_enabled:
            raise TradingDisabledError()

    async def _enforce_amount_cap(self, payload: CreateOrderRequest) -> None:
        """Enforce the KRW notional cap on a new order.

        Limit orders use the caller-supplied price. Market orders fetch
        the current last-traded price from KIS and compute the notional
        against that — the "market orders skip the cap" loophole from
        the Phase 2 security review has been closed.
        """
        if payload.order_type == OrderType.MARKET:
            last_price = await self._fetch_last_price(payload.symbol)
            self._check_amount_cap_raw(quantity=payload.quantity, price=last_price)
            return
        if payload.price is None:
            # Limit order without a price should have been rejected by
            # the pydantic validator; defensive raise keeps the contract.
            raise OrderFailedError("Limit orders require a price")
        self._check_amount_cap_raw(quantity=payload.quantity, price=payload.price)

    def _check_amount_cap_raw(self, *, quantity: int, price: int) -> None:
        amount = quantity * price
        if amount > self._settings.trading_max_order_amount:
            raise OrderAmountExceededError(amount, self._settings.trading_max_order_amount)

    async def _fetch_last_price(self, symbol: str) -> int:
        try:
            price_resp = await self._kis.inquire_stock_price(symbol)
        except InvalidSymbolError as exc:
            raise OrderFailedError(f"Symbol not tradable: {symbol}") from exc
        last_price = to_int(price_resp.output.price)
        if last_price <= 0:
            raise OrderFailedError("Market order cap check failed: KIS returned no last-traded price")
        return last_price

    # ------------------------------------------------------------------
    # Logging — WARNING level for real mode, INFO for mock
    # ------------------------------------------------------------------

    def _log_order_attempt(
        self,
        action: str,
        payload: CreateOrderRequest,
        price: int,
    ) -> None:
        amount = payload.quantity * price if payload.order_type == OrderType.LIMIT else None
        extra = {
            "action": action,
            "account_mode": self._settings.kis_account_mode.value,
            "symbol": payload.symbol,
            "side": payload.side.value,
            "order_type": payload.order_type.value,
            "quantity": payload.quantity,
            "price": price,
            "amount": amount,
        }
        if self._settings.kis_account_mode == AccountMode.REAL:
            logger.warning("trading order attempt", extra=extra)
        else:
            logger.info("trading order attempt", extra=extra)

    def _log_order_mutation(self, action: str, order_id: str, **context: object) -> None:
        extra = {
            "action": action,
            "account_mode": self._settings.kis_account_mode.value,
            "order_id": order_id,
            **context,
        }
        if self._settings.kis_account_mode == AccountMode.REAL:
            logger.warning("trading order mutation", extra=extra)
        else:
            logger.info("trading order mutation", extra=extra)

    # ------------------------------------------------------------------
    # KIS response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_if_kis_rejected(response: OrderCashResponse) -> None:
        if response.rt_cd != "0":
            message = response.msg1 or "KIS rejected the order"
            raise OrderFailedError(message, kis_msg_cd=response.msg_cd)

    @staticmethod
    def _require_output(response: OrderCashResponse):
        if response.output is None:
            raise OrderFailedError("KIS returned rt_cd=0 without an output body")
        return response.output

    @staticmethod
    def _compose_order_id(branch: str, odno: str) -> str:
        return f"{branch}{_ORDER_ID_SEPARATOR}{odno}" if branch else odno

    @staticmethod
    def _parse_order_id(order_id: str) -> tuple[str, str]:
        """Validate + split the public `order_id` into `(branch, odno)`.

        Raises `OrderNotFoundError` on malformed input — this is the
        user-facing status (404) for both "id was garbage" and "id was
        valid but not in history".
        """
        match = _ORDER_ID_RE.match(order_id)
        if match is None:
            raise OrderNotFoundError(order_id)
        branch = match.group(1) or ""
        odno = match.group(2)
        return branch, odno

    @staticmethod
    def _parse_kis_time(raw: str) -> datetime | None:
        """Parse a KIS `HHMMSS` KST timestamp into a UTC-aware datetime."""
        if not raw or len(raw) != 6:
            return None
        try:
            hour, minute, second = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
        except ValueError:
            return None
        kst_now = datetime.now(_KST)
        kst_time = kst_now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return kst_time.astimezone(UTC)

    def _executions_from(self, response: DailyCcldResponse) -> list[OrderExecution]:
        executions: list[OrderExecution] = []
        for row in response.output1:
            quantity = to_int(row.order_quantity)
            filled = to_int(row.filled_quantity)
            status = self._classify_status(row.cancel_yn, quantity, filled)
            composite = self._compose_order_id(row.branch_office, row.order_id)
            executions.append(
                OrderExecution(
                    order_id=row.order_id,
                    branch_office=row.branch_office,
                    composite_id=composite,
                    symbol=row.symbol,
                    name=row.name or row.symbol,
                    side=_KIS_SIDE_TO_ENUM.get(row.side_code, OrderSide.BUY),
                    order_type=_KIS_ORDER_TYPE_TO_ENUM.get(row.order_type_code, OrderType.LIMIT),
                    quantity=quantity,
                    filled_quantity=filled,
                    price=to_int(row.order_price),
                    status=status,
                    submitted_at=self._parse_kis_time(row.order_time),
                )
            )
        return executions

    @staticmethod
    def _classify_status(cancel_yn: str, quantity: int, filled: int) -> OrderStatus:
        if cancel_yn == "Y":
            return OrderStatus.CANCELLED
        if filled == 0:
            return OrderStatus.SUBMITTED
        if filled < quantity:
            return OrderStatus.PARTIAL
        return OrderStatus.FILLED

    def _to_order_response(self, row: OrderExecution) -> OrderResponse:
        return OrderResponse(
            order_id=row.composite_id,
            symbol=row.symbol,
            name=row.name,
            side=row.side,
            order_type=row.order_type,
            quantity=row.quantity,
            price=row.price if row.price > 0 else None,
            filled_quantity=row.filled_quantity,
            status=row.status,
            submitted_at=row.submitted_at,
            account_mode=self._settings.kis_account_mode,
        )
