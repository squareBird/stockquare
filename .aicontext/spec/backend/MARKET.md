# Market Spec

Market-wide data (indices, later: sector performance, breadth). Domain-owned; used by the Dashboard market card and future Market Overview page.

## 1. Market Indices

### GET /api/v1/market/indices

Returns current KOSPI and KOSDAQ index data, enriched with a KRX trading-session status computed from the KST wall clock.

**Response**:
```json
{
  "indices": [
    {
      "code": "0001",
      "name": "KOSPI",
      "value": 2650.32,
      "change": 15.20,
      "change_rate": 0.58,
      "volume": 450000000,
      "status": "open"
    },
    {
      "code": "1001",
      "name": "KOSDAQ",
      "value": 870.15,
      "change": -3.40,
      "change_rate": -0.39,
      "volume": 620000000,
      "status": "open"
    }
  ],
  "errors": []
}
```

**Partial-failure response** (KOSDAQ fails, KOSPI survives):
```json
{
  "indices": [
    { "code": "0001", "name": "KOSPI", "value": 2650.32, "change": 15.20, ... }
  ],
  "errors": [
    {
      "code": "1001",
      "name": "KOSDAQ",
      "error_code": "KIS_API_ERROR",
      "message": "Upstream KIS request failed"
    }
  ]
}
```

The response is **HTTP 200** whenever at least one index succeeds. The frontend
renders healthy cards from `indices` and degraded skeletons for each entry in
`errors`. Only when **every** index fetch fails does the endpoint return
HTTP 502 `KIS_API_ERROR`.

**Response Model**:
```python
class MarketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    POST_MARKET = "post_market"

class MarketIndexResponse(BaseModel):
    code: str                   # Index code (0001=KOSPI, 1001=KOSDAQ)
    name: str
    value: float                # Current index value
    change: float               # Change from previous close
    change_rate: float          # Change rate (%)
    volume: int                 # Accumulated trading volume
    status: MarketStatus

class MarketIndexErrorResponse(BaseModel):
    code: str                   # Index code that failed
    name: str                   # Human-readable name
    error_code: str             # StockquareError code (e.g. KIS_API_ERROR)
    message: str                # Short human-readable message

class MarketIndicesResponse(BaseModel):
    indices: list[MarketIndexResponse]
    errors: list[MarketIndexErrorResponse]  # per-index failures; empty on full success
```

### Market Status Computation

KRX regular session: 09:00–15:30 KST, Mon–Fri. The backend derives `status` from `datetime.now(UTC) + 9h`:

| KST Time | Day | Status |
|----------|-----|--------|
| 09:00–15:30 | Mon–Fri | `open` |
| 08:00–09:00 | Mon–Fri | `pre_market` |
| 15:30–18:00 | Mon–Fri | `post_market` |
| All other times / weekends | — | `closed` |

### KIS API Mapping

| Field | KIS Endpoint | tr_id | KIS Field |
|-------|-------------|-------|-----------|
| value | `/uapi/domestic-stock/v1/quotations/inquire-index-price` | `FHPUP02100000` | `bstp_nmix_prpr` |
| change | Same | Same | `bstp_nmix_prdy_vrss` |
| change_rate | Same | Same | `bstp_nmix_prdy_ctrt` |
| volume | Same | Same | `acml_vol` |

### KIS Request Details

```
GET {base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price
Headers:
  authorization: Bearer {token}
  appkey: {app_key}
  appsecret: {app_secret}
  tr_id: FHPUP02100000
Query:
  FID_COND_MRKT_DIV_CODE: "U"
  FID_INPUT_ISCD: "0001"  # 0001=KOSPI, 1001=KOSDAQ
```

Calls for KOSPI and KOSDAQ are issued in parallel via
`asyncio.gather(..., return_exceptions=True)` so a single upstream failure
never takes down the entire endpoint. KIS is known to return HTTP 500 for
`inquire-index-price` on one index code while the sibling call succeeds.

### Supported Indices

| Code | Name | Description |
|------|------|-------------|
| `0001` | KOSPI | Korea Composite Stock Price Index |
| `1001` | KOSDAQ | Korean Securities Dealers Automated Quotations |

## 2. Error Handling

| Scenario | HTTP Status | Code | Description |
|----------|-------------|------|-------------|
| KIS credentials missing | 503 | `KIS_NOT_CONFIGURED` | Core KIS credentials not set — fail-fast before network I/O |
| Partial KIS failure (1 of 2 indices down) | 200 | — | Degraded response with `errors[]` entry for the failed slot |
| All indices failed | 502 | `KIS_API_ERROR` | Full upstream outage |

## 3. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Market endpoints | `app/api/v1/market.py` | api |
| Market service | `app/services/market.py` | services |
| KIS client | `app/kis/client.py` | kis |
| KIS response models | `app/kis/models.py` | kis |

## 4. Phase 2 Extensions (placeholder)

- `GET /api/v1/market/sectors` — Sector performance ranking
- `GET /api/v1/market/top-movers` — Top gainers / losers
