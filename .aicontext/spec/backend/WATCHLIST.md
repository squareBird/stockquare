# Watchlist Spec

User-managed list of symbols persisted in the local database and enriched with real-time KIS price data on read. Domain-owned; used by the Dashboard watchlist card and the Trading page's quick-access list.

## 1. Endpoints

### GET /api/v1/watchlist

Returns all watchlist items with current price data.

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "symbol": "005930",
      "name": "삼성전자",
      "price": 72000,
      "change": 1500,
      "change_rate": 2.13,
      "volume": 15234000,
      "sort_order": 0,
      "created_at": "2026-04-10T09:00:00"
    }
  ],
  "errors": [],
  "count": 1
}
```

**Partial-failure response** (KIS price lookup fails for a specific symbol):
```json
{
  "items": [
    { "id": 1, "symbol": "005930", "name": "삼성전자", "price": 72000, ... }
  ],
  "errors": [
    {
      "id": 2,
      "symbol": "000660",
      "sort_order": 1,
      "error_code": "KIS_API_ERROR",
      "message": "Upstream KIS request failed"
    }
  ],
  "count": 2
}
```

The response is HTTP 200 whenever the DB query succeeded. `count` is the
total number of rows in the watchlist (`items + errors`). The frontend
renders `items` as healthy cards and `errors` as degraded skeletons with a
retry affordance.

**Response Model**:
```python
class WatchlistItemResponse(BaseModel):
    id: int
    symbol: str
    name: str                   # Korean name from the in-memory master index
    price: int                  # Current price (KRW)
    change: int                 # Change from previous close (KRW)
    change_rate: float          # Change rate (%)
    volume: int                 # Accumulated volume
    sort_order: int
    created_at: datetime

class WatchlistItemError(BaseModel):
    id: int
    symbol: str
    sort_order: int
    error_code: str             # StockquareError code (e.g. KIS_API_ERROR)
    message: str                # Short human-readable message

class WatchlistResponse(BaseModel):
    items: list[WatchlistItemResponse]
    errors: list[WatchlistItemError]   # per-item enrichment failures
    count: int                         # items + errors
```

**Name enrichment**:
- Watchlist item names are **resolved from the in-memory master index**
  (`name_ko`, falling back to `name_en`) at read time, keyed by symbol.
  KIS `inquire-price` is used only for the live price/change/volume — it
  carries no stock name (`hts_kor_isnm` is not in its output), so it cannot
  be the name source. The DB persists a best-effort name at add time but the
  read path always re-resolves from the index, so an index refresh (renamed /
  relisted symbol) reflects without any migration. When the index has no row
  for a symbol (e.g. a freshly listed code not yet in the snapshot), the name
  falls back to the stored value, then the symbol.
- Failed price enrichments surface in `errors[]` keyed by `symbol` (no `name`
  field — the frontend already knows the symbol is the sort-stable key).

**Degradation**:
- Empty watchlist returns `{"items": [], "errors": [], "count": 0}` without
  any KIS calls.
- If KIS price lookup fails for a specific symbol, that symbol moves into
  `errors[]` with its `sort_order` preserved. The rest of the response is
  unaffected and the HTTP status stays 200.

### POST /api/v1/watchlist

Add a symbol to the watchlist.

**Request**:
```json
{
  "symbol": "005930"
}
```

**Request Model**:
```python
class WatchlistAddRequest(BaseModel):
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
```

**Response**: `201 Created`
```json
{
  "id": 1,
  "symbol": "005930",
  "name": "삼성전자",
  "sort_order": 0,
  "created_at": "2026-04-10T09:00:00"
}
```

`name` is resolved from the master index at add time (best effort) and
re-resolved on every `GET /watchlist` read — see §2 Name Enrichment.

**Validation**:
- Reject duplicate symbols (409 Conflict, `DUPLICATE_SYMBOL`).
- Verify the symbol exists by calling KIS stock info API before saving.
- Maximum 20 items per watchlist (400, `WATCHLIST_FULL`).

### DELETE /api/v1/watchlist/{item_id}

Remove a symbol from the watchlist.

**Response**: `204 No Content`

**Validation**:
- Return 404 `NOT_FOUND` if `item_id` does not exist.

### PATCH /api/v1/watchlist/reorder

Update sort order for watchlist items.

**Request**:
```json
{
  "order": [
    { "id": 1, "sort_order": 0 },
    { "id": 2, "sort_order": 1 }
  ]
}
```

**Request Model**:
```python
class WatchlistOrderItem(BaseModel):
    id: int
    sort_order: int = Field(ge=0)

class WatchlistReorderRequest(BaseModel):
    order: list[WatchlistOrderItem]
```

**Response**: `200 OK`
```json
{
  "updated": 2
}
```

**Validation**:
- Every `id` in the payload must exist. Missing any id → 404 `NOT_FOUND`.

## 2. KIS Price Enrichment

When returning watchlist items, enrich each symbol with real-time price data
from KIS in parallel. The Korean name is **not** part of the price response —
it is resolved separately from the in-memory master index (see §2 Name
Enrichment), so `GET /watchlist` reflects the current canonical name without
an extra KIS call.

| Field | KIS Endpoint | tr_id | KIS Field |
|-------|-------------|-------|-----------|
| price | `/uapi/domestic-stock/v1/quotations/inquire-price` | `FHKST01010100` | `stck_prpr` |
| change | Same | Same | `prdy_vrss` |
| change_rate | Same | Same | `prdy_ctrt` |
| volume | Same | Same | `acml_vol` |
| name (Korean) | _master index_ (`StockMasterIndex.by_symbol`) | — | `name_ko` / `name_en` |

Price lookups are issued via `asyncio.gather(..., return_exceptions=True)`
so a single failure only routes that one symbol into `errors[]`. KIS is
known to return HTTP 500 on individual quote lookups while sibling symbols
succeed; this pattern keeps the watchlist card healthy under partial
upstream outages.

## 3. Database Schema

```sql
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(6) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_watchlist_sort_order ON watchlist (sort_order);
```

The unique index on `symbol` backstops any race between concurrent adds: if the count check races, the subsequent insert raises `IntegrityError` which is mapped to `DuplicateSymbolError`.

## 4. Error Handling

| Scenario | HTTP Status | Code | Description |
|----------|-------------|------|-------------|
| Symbol not found in KIS (add) | 400 | `INVALID_SYMBOL` | Symbol does not exist |
| Duplicate (add) | 409 | `DUPLICATE_SYMBOL` | Symbol already in watchlist |
| Watchlist full (add) | 400 | `WATCHLIST_FULL` | Maximum 20 items reached |
| Item not found (delete / reorder) | 404 | `NOT_FOUND` | Watchlist item id does not exist |
| KIS API failure during add / mutation | 502 | `KIS_API_ERROR` | Upstream KIS request failed |
| KIS credentials missing during add / mutation | 503 | `KIS_NOT_CONFIGURED` | Core KIS credentials not set |
| Partial enrichment failure on `GET /watchlist` | **200** | — | Failed items surface in `errors[]`; healthy items stay in `items[]` |

## 5. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Watchlist endpoints | `app/api/v1/watchlist.py` | api |
| Watchlist service | `app/services/watchlist.py` | services |
| Watchlist DB model | `app/db/models.py` | db |
| Watchlist domain model | `app/models/watchlist.py` | models |
| KIS client (price) | `app/kis/client.py` | kis |
| Exception classes | `app/core/exceptions.py` | core |
