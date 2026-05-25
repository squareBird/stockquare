# Portfolio Spec

Portfolio-scoped backend API providing account summary and holdings overview. Domain-owned; reusable across Dashboard, Trading, and Portfolio pages on the frontend.

## 1. Account Summary

### GET /api/v1/portfolio/summary

Returns total asset value, daily profit/loss, and holdings overview for the authenticated account.

**Response** (both KIS calls succeed):
```json
{
  "total_asset": 15230000,
  "total_purchase": 14500000,
  "total_profit": 730000,
  "total_profit_rate": 5.03,
  "daily_profit": 120000,
  "daily_profit_rate": 0.79,
  "cash_balance": 3200000,
  "holdings_count": 5,
  "errors": []
}
```

**Partial-failure response** (`inquire-balance` fails, summary survives):
```json
{
  "total_asset": 15230000,
  "total_purchase": 14500000,
  "total_profit": 730000,
  "total_profit_rate": 5.03,
  "daily_profit": 120000,
  "daily_profit_rate": 0.79,
  "cash_balance": null,
  "holdings_count": null,
  "errors": [
    { "field": "cash_balance", "error_code": "KIS_API_ERROR", "message": "Upstream KIS request failed" },
    { "field": "holdings_count", "error_code": "KIS_API_ERROR", "message": "Upstream KIS request failed" }
  ]
}
```

The response is HTTP 200 whenever **any** KIS data source succeeds. When
every source fails, the endpoint escalates to HTTP 502 `KIS_API_ERROR` or
HTTP 503 `KIS_NOT_CONFIGURED` (if the failure was caused by missing
credentials).

**Response Model**:
```python
class PortfolioFieldError(BaseModel):
    field: str                  # e.g. "cash_balance", "total_asset"
    error_code: str             # StockquareError code
    message: str                # Short human-readable message

class AccountSummaryResponse(BaseModel):
    # From inquire-account-balance
    total_asset: int | None          # Total evaluated asset (KRW)
    total_purchase: int | None       # Total purchase amount (KRW)
    total_profit: int | None         # Total unrealized P&L (KRW)
    total_profit_rate: float | None  # Total P&L rate (%)
    daily_profit: int | None         # Daily P&L (KRW)
    daily_profit_rate: float | None  # Daily P&L rate (derived; needs total_asset)
    # From inquire-balance
    cash_balance: int | None         # Available cash (KRW)
    holdings_count: int | None       # Number of stocks held
    # Per-data-source failures (empty when both KIS calls succeeded)
    errors: list[PortfolioFieldError]
```

### Degradation Behavior

- `inquire-account-balance` populates the account summary fields. If it
  fails, those fields are `null` and an entry per field is appended to
  `errors`.
- `inquire-balance` populates `cash_balance` + `holdings_count`. If it
  fails, those two fields are `null` and two `errors` entries are
  appended.
- `daily_profit_rate` is computed from `daily_profit / total_asset`; it
  requires both inputs to populate. When `total_asset` is missing the
  derived field is left `null`.

### KIS API Mapping

| Field | KIS Endpoint | tr_id (Real/Mock) | KIS Field |
|-------|-------------|-------------------|-----------|
| total_asset | `/uapi/domestic-stock/v1/trading/inquire-account-balance` | `CTRP6548R` / `VTRP6548R` | `tot_asst_amt` |
| total_purchase | Same | Same | `pchs_amt_smtl` |
| total_profit | Same | Same | `evlu_pfls_smtl` |
| total_profit_rate | Same | Same | `evlu_pfls_rt` |
| daily_profit | Same | Same | `bfdy_cprs_pfls` |
| daily_profit_rate | Computed | — | `(daily_profit / total_asset) * 100` |
| cash_balance | `/uapi/domestic-stock/v1/trading/inquire-balance` | `TTTC8434R` / `VTTC8434R` | `dnca_tot_amt` |
| holdings_count | Same (list length) | Same | Count of `output1` items |

### KIS Request Details

**Account Balance Inquiry**:
```
GET {base_url}/uapi/domestic-stock/v1/trading/inquire-balance
Headers:
  authorization: Bearer {token}
  appkey: {app_key}
  appsecret: {app_secret}
  tr_id: TTTC8434R (real) / VTTC8434R (mock)
Query:
  CANO: {account_no}
  ACNT_PRDT_CD: {product_code}
  AFHR_FLPR_YN: "N"
  OFL_YN: ""
  INQR_DVSN: "02"
  UNPR_DVSN: "01"
  FUND_STTL_ICLD_YN: "N"
  FNCG_AMT_AUTO_RDPT_YN: "N"
  PRCS_DVSN: "00"
  CTX_AREA_FK100: ""
  CTX_AREA_NK100: ""
```

**Account Balance Summary**:
```
GET {base_url}/uapi/domestic-stock/v1/trading/inquire-account-balance
Headers:
  authorization: Bearer {token}
  appkey: {app_key}
  appsecret: {app_secret}
  tr_id: CTRP6548R (real) / VTRP6548R (mock)
Query:
  CANO: {account_no}
  ACNT_PRDT_CD: {product_code}
  INQR_DVSN_1: ""
  BSPR_BF_DT_APLY_YN: ""
```

## 2. Error Handling

| Scenario | HTTP Status | Code | Description |
|----------|-------------|------|-------------|
| KIS credentials missing (both calls) | 503 | `KIS_NOT_CONFIGURED` | Backend started without core KIS credentials |
| KIS API failure (both calls) | 502 | `KIS_API_ERROR` | Every upstream KIS request failed |
| Token expired (mid-request) | 401 | `TOKEN_EXPIRED` | Access token expired; auto-refresh attempted once |
| Partial KIS failure | **200** | — | Degraded response with `null` fields + `errors[]` entries |

## 3. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Portfolio endpoints | `app/api/v1/portfolio.py` | api |
| Portfolio service | `app/services/portfolio.py` | services |
| KIS client | `app/kis/client.py` | kis |
| KIS response models | `app/kis/models.py` | kis |
| Domain response model | `app/models/portfolio.py` (or inline in router) | models |
| Exception classes | `app/core/exceptions.py` | core |

## 4. Holdings API

### GET /api/v1/portfolio/holdings

Returns a per-symbol list of the authenticated account's current stock
holdings with live price data and realized purchase context. Used by the
Portfolio page for the "내 보유 종목" table and by the Dashboard holdings
drawer.

**Response (full success)**:
```json
{
  "holdings": [
    {
      "symbol": "005930",
      "name": "삼성전자",
      "quantity": 10,
      "avg_purchase_price": 71000,
      "current_price": 72300,
      "evaluation_amount": 723000,
      "purchase_amount": 710000,
      "profit": 13000,
      "profit_rate": 1.83
    }
  ],
  "errors": [],
  "count": 1
}
```

**Empty portfolio** (no holdings but KIS call succeeded):
```json
{ "holdings": [], "errors": [], "count": 0 }
```

**Response Model**:
```python
class Holding(BaseModel):
    symbol: str
    name: str                    # Live Korean name from KIS (hts_kor_isnm / prdt_name)
    quantity: int
    avg_purchase_price: int      # KRW, integer (KIS returns fractional but we floor)
    current_price: int           # KRW
    evaluation_amount: int       # quantity × current_price
    purchase_amount: int         # quantity × avg_purchase_price
    profit: int                  # evaluation_amount − purchase_amount
    profit_rate: float           # (profit / purchase_amount) * 100

class HoldingsResponse(BaseModel):
    holdings: list[Holding]
    errors: list[PortfolioFieldError]  # reused from summary schema
    count: int                   # len(holdings) + len(errors)
```

### KIS API Mapping

Holdings come from the same `inquire-balance` call used by the summary
endpoint — the `output1` array contains one row per held symbol. No extra
KIS traffic beyond the single call.

| Field | KIS Endpoint | tr_id (Real/Mock) | KIS Field |
|-------|-------------|-------------------|-----------|
| symbol | `/uapi/domestic-stock/v1/trading/inquire-balance` | `TTTC8434R` / `VTTC8434R` | `pdno` |
| name | Same | Same | `prdt_name` |
| quantity | Same | Same | `hldg_qty` |
| avg_purchase_price | Same | Same | `pchs_avg_pric` |
| current_price | Same | Same | `prpr` |
| evaluation_amount | Same | Same | `evlu_amt` |
| purchase_amount | Same | Same | `pchs_amt` |
| profit | Same | Same | `evlu_pfls_amt` |
| profit_rate | Same | Same | `evlu_pfls_rt` |

### Degradation Behavior

- KIS call succeeds → `holdings[]` populated, `errors[]` empty, 200 OK.
- KIS call fails (any reason — 5xx, timeout, network) → `holdings[]` empty,
  `errors[]` contains a single `PortfolioFieldError(field="holdings", ...)`
  entry, HTTP 502 (full failure).
- KIS call succeeds but returns an empty `output1` array → `holdings[]`
  empty, `errors[]` empty, 200 OK with `count: 0`.
- KIS credentials missing → 503 `KIS_NOT_CONFIGURED` (fail-fast).

## 5. Phase 2 Extensions (placeholder, not implemented)

- `GET /api/v1/portfolio/history` — Historical P&L series for charting
