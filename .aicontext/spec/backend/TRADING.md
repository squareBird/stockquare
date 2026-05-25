# Trading Spec

Order placement, modification, cancellation, and history — the money-moving
surface of the Stockquare backend. Every mutation passes through two safety
gates before reaching KIS.

## 1. Endpoints

All trading endpoints live under `/api/v1/orders`.

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/api/v1/orders` | Create a new cash order (buy or sell) |
| GET    | `/api/v1/orders` | List recent orders from the KIS daily-ccld feed |
| GET    | `/api/v1/orders/{order_id}` | Fetch a single order by its composite id |
| DELETE | `/api/v1/orders/{order_id}` | Cancel an outstanding order |
| PATCH  | `/api/v1/orders/{order_id}` | Modify the quantity and/or price of an outstanding order |

## 2. Request / Response Models

### Create order
```json
POST /api/v1/orders
{
  "symbol": "005930",
  "side": "buy",
  "order_type": "limit",
  "quantity": 1,
  "price": 72000
}
```

- `symbol` — 6-digit KRX code
- `side` — `"buy"` or `"sell"`
- `order_type` — `"limit"` or `"market"`
- `quantity` — positive integer
- `price` — KRW per share; required when `order_type=limit`, ignored when `order_type=market` (send `null` or omit)

Response (`201 Created`):
```json
{
  "order_id": "01234-0000012345",
  "symbol": "005930",
  "name": "삼성전자",
  "side": "buy",
  "order_type": "limit",
  "quantity": 1,
  "price": 72000,
  "filled_quantity": 0,
  "status": "submitted",
  "submitted_at": "2026-04-11T09:30:14+00:00",
  "account_mode": "real"
}
```

`order_id` is a composite of the KIS branch office code (`KRX_FWDG_ORD_ORGNO`)
and the order number (`ODNO`), joined by `-`. The frontend should treat it
as an opaque string.

### List orders
```
GET /api/v1/orders
```
Returns `{"orders": [...], "count": N}`. The backend queries KIS
`inquire-daily-ccld` for the last 7 days by default. Frontends that need
longer windows should switch to a paginated endpoint in Phase 2.1 (not
implemented yet).

### Get single order
```
GET /api/v1/orders/{order_id}
```
Returns a single `OrderResponse` or `404 NOT_FOUND` if the id is not in
the recent history window.

### Cancel order
```
DELETE /api/v1/orders/{order_id}
```
Returns `{"order_id": "...", "cancelled": true}` on success, propagates
KIS errors otherwise.

### Modify order
```
PATCH /api/v1/orders/{order_id}
{ "quantity": 2, "price": 71500 }
```
Both fields are required — no partial modify. The modified order gets a
**new** `order_id` from KIS and is returned with the `submitted` status.

## 3. Order Status State Machine

```
submitted ──► partial ──► filled
    │             │
    └─► cancelled ┘
    │
    └─► rejected  (KIS refused at submission time)
```

Status is derived from KIS `inquire-daily-ccld` on read:

| KIS field | Value | Stockquare status |
|-----------|-------|-------------------|
| `cncl_yn` | `Y` | `cancelled` |
| `tot_ccld_qty` | `0` | `submitted` |
| `tot_ccld_qty < ord_qty` | | `partial` |
| `tot_ccld_qty == ord_qty` | | `filled` |

`rejected` is only seen at create-time: when KIS returns `rt_cd != "0"`
on `order-cash`, the service raises `OrderFailedError` (400) with the KIS
`msg1` echoed back to the caller.

## 4. KIS API Mapping

| Operation | Endpoint | Real tr_id | Mock tr_id |
|-----------|----------|-----------|------------|
| Buy (현금 매수) | `/uapi/domestic-stock/v1/trading/order-cash` | `TTTC0802U` | `VTTC0802U` |
| Sell (현금 매도) | `/uapi/domestic-stock/v1/trading/order-cash` | `TTTC0801U` | `VTTC0801U` |
| Cancel / Modify | `/uapi/domestic-stock/v1/trading/order-rvsecncl` | `TTTC0803U` | `VTTC0803U` |
| Daily execution list (≤3 months) | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | `TTTC0081R` | `VTTC0081R` |
| Daily execution list (>3 months) | Same endpoint | `CTSC9215R` | `VTSC9215R` (out of scope in Phase 2) |

> **tr_id verification note**: `order-cash`, `order-rvsecncl`, and the
> within-3-months variant of `inquire-daily-ccld` were verified against
> `koreainvestment/open-trading-api` `examples_llm/` and `legacy/rest/`
> sources during Phase 2 research. An earlier guess of `TTTC8001R`
> for `inquire-daily-ccld` came from the legacy code path and was
> corrected to `TTTC0081R` before merge. The >3-months tr_ids
> (`CTSC9215R` / `VTSC9215R`) are reserved for a future pagination
> extension. Any KIS tr_id mismatch surfaces as `rt_cd="1"` plus a
> specific `msg_cd` in the response — the enhanced logging in
> `_log_kis_error_body` (Phase 1) captures these for diagnosis.

### order-cash body

```
POST {base_url}/uapi/domestic-stock/v1/trading/order-cash
Headers:
  authorization: Bearer {token}
  appkey / appsecret / tr_id / custtype: P / content-type: application/json
Body:
  CANO: {account_no}
  ACNT_PRDT_CD: {product_code}
  PDNO: {symbol}
  ORD_DVSN: "00" (limit) | "01" (market)
  ORD_QTY: {quantity}
  ORD_UNPR: {price}  # "0" for market orders
```

### order-rvsecncl body

```
POST {base_url}/uapi/domestic-stock/v1/trading/order-rvsecncl
Body:
  CANO / ACNT_PRDT_CD — account identifiers
  KRX_FWDG_ORD_ORGNO — branch office from the original order
  ORGN_ODNO — original order number
  ORD_DVSN — "00" (limit) | "01" (market); must match the original order
  RVSE_CNCL_DVSN_CD — "01" (modify) | "02" (cancel)
  ORD_QTY / ORD_UNPR — new values (ignored on cancel)
  QTY_ALL_ORD_YN — "Y" on cancel, "N" on modify
```

## 5. Safety Gates

### TRADING_REAL_MODE_ENABLED (env var, default `true`)
When `KIS_ACCOUNT_MODE=real` and this flag is `false`, every mutation
(`POST`, `PATCH`, `DELETE`) raises `TradingDisabledError` (HTTP 403
`TRADING_DISABLED`) before touching KIS. Read-only `GET` paths are
unaffected. Flip to `false` to run the backend in real mode purely for
read access while blocking accidental orders during testing.

### TRADING_MAX_ORDER_AMOUNT (env var, default `50000` KRW)
For **limit** orders, `quantity × price` is compared against this cap
before the KIS call. Orders above the cap raise `OrderAmountExceededError`
(HTTP 400 `ORDER_AMOUNT_EXCEEDED`) with the offending amount + configured
limit echoed in the message.

**Market orders skip the cap** — there is no known KRW value at
submission time, so the account-level balance remains the natural
guardrail. Phase 1.5 user balance (~500 KRW) makes this safe in practice.

### Structured logging
Every create / modify / cancel attempt is logged:

- `WARNING` level in `real` mode
- `INFO` level in `mock` mode
- `extra` fields: `action`, `account_mode`, `symbol`, `side`, `order_type`,
  `quantity`, `price`, `amount`, `order_id`

Credentials are **never** logged. Only business-level fields above.

## 6. Error Handling

| Scenario | HTTP | Code |
|----------|------|------|
| Trading disabled in real mode | 403 | `TRADING_DISABLED` |
| Order amount exceeds cap (limit order) | 400 | `ORDER_AMOUNT_EXCEEDED` |
| Pydantic validation (bad symbol / negative qty / missing price on limit) | 422 | — |
| KIS rejected the order (rt_cd != "0") | 400 | `ORDER_FAILED` (includes `msg_cd`/`msg1`) |
| Order id not in recent history | 404 | `ORDER_NOT_FOUND` |
| KIS credentials missing | 503 | `KIS_NOT_CONFIGURED` |
| KIS API failure (5xx / network) | 502 | `KIS_API_ERROR` |
| Access token expired | 401 | `TOKEN_EXPIRED` |

## 7. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Trading endpoints | `app/api/v1/trading.py` | api |
| Trading service | `app/services/trading.py` | services |
| Domain models | `app/models/trading.py` | models |
| KIS client methods | `app/kis/client.py` (`order_cash`, `order_revise_cancel`, `inquire_daily_ccld`) | kis |
| KIS response models | `app/kis/models.py` (`OrderCashResponse`, `DailyCcldResponse`) | kis |
| Exception classes | `app/core/exceptions.py` (`TradingDisabledError`, `OrderAmountExceededError`, `OrderFailedError`, `OrderNotFoundError`) | core |
| Settings | `app/core/config.py` (`trading_real_mode_enabled`, `trading_max_order_amount`) | core |

## 8. Phase 2.1 Extensions (placeholder, not implemented)

- Paginated history (`GET /orders?from_date=&to_date=&cursor=`)
- Conditional orders (stop-loss, trailing)
- Bulk cancel
- WebSocket order-state stream (replaces daily-ccld polling)
