# Stocks Spec

Stock-level metadata lookups (search, info, later: quote history, fundamentals). Domain-owned; used by the Watchlist add-modal and future Stock Detail pages.

## 1. Stock Search

Lightweight search endpoint. Debouncing is the frontend's responsibility; the backend performs a single KIS lookup per call.

### GET /api/v1/stocks/search

**Query Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `q` | string | Yes | — | Symbol (6-digit) or partial Korean/English name, minimum 1 character |
| `limit` | int | No | 10 | Maximum results (1–50) |

**Response**:
```json
{
  "items": [
    {
      "symbol": "005930",
      "name": "Samsung Electronics",
      "market": "KOSPI"
    },
    {
      "symbol": "000660",
      "name": "SK Hynix",
      "market": "KOSPI"
    }
  ],
  "count": 2
}
```

**Response Model**:
```python
class StockMarket(str, Enum):
    KOSPI = "KOSPI"
    KOSDAQ = "KOSDAQ"
    NASDAQ = "NASDAQ"
    NYSE = "NYSE"
    AMEX = "AMEX"

class StockSearchItem(BaseModel):
    symbol: str
    name: str
    market: StockMarket

class StockSearchResponse(BaseModel):
    items: list[StockSearchItem]
    count: int
```

**Validation**:
- Empty query → 400 `INVALID_QUERY`.
- `limit` out of range → 400 (FastAPI query validation).

### Behavior

- When `q` is a valid 6-digit code, the backend attempts a direct `inquire-price` lookup first, then uses `search-info` to classify the market. This path stays on the live KIS quote API so the returned name is always the authoritative HTS name.
- When `q` is text, the backend serves results from the in-memory Local Master Index (see below). Ranking is tier-based: exact symbol match, then exact name, then prefix, then substring; ties break on market order (KOSPI → KOSDAQ → NASDAQ → NYSE → AMEX). Search is case-insensitive and NFC-normalized. Up to `limit` rows are returned.
- Unknown symbols, KIS failures, and empty-index states all return `{"items": [], "count": 0}` rather than an error — the search box must never show a red failure state for a legitimate empty result.

### Local Master Index

On startup the backend downloads five flat-file stock listings from the KIS public CDN and parses them into an in-memory index. There is no background refresh daemon in Phase 1 — the index is rebuilt only on process restart.

**Source**: `https://new.real.download.dws.co.kr/common/master/`

| Market | File | Format |
|--------|------|--------|
| KOSPI | `kospi_code.mst.zip` | CP949, fixed-width lines |
| KOSDAQ | `kosdaq_code.mst.zip` | CP949, fixed-width lines |
| NASDAQ | `nasmst.cod.zip` | CP949, tab-delimited |
| NYSE | `nysmst.cod.zip` | CP949, tab-delimited |
| AMEX | `amsmst.cod.zip` | CP949, tab-delimited |

**On-disk cache**: parsed rows are persisted to `backend/.cache/kis_master/{market}.jsonl` with a 24-hour TTL. Restarts within that window skip the download and load from disk.

**Known limitations**:
- The KR master files do not publish an English name column, so an English-language query such as `"samsung"` does not match `005930` via the KR rows. Users searching in English for a KR stock will get zero results. Users typing `"삼성"` or `"005930"` work as expected.
- Halted / delisted filtering is deferred — the Part 2 suspension flags are not yet parsed, so a handful of inactive symbols may appear in search results until the next snapshot drops them.
- US security-type filtering keeps only common stock (column 8 == `"2"`). Warrants, preferred, and ETFs with a different type flag are excluded from search.
- No Korean 초성 (initial consonant) search and no romanization (e.g. `"samseong"`). Out of scope for Phase 1.

### KIS API Mapping

| Field | KIS Endpoint | tr_id | KIS Field |
|-------|-------------|-------|-----------|
| name (by code) | `/uapi/domestic-stock/v1/quotations/inquire-price` | `FHKST01010100` | `hts_kor_isnm` |
| symbol (by name) | `/uapi/domestic-stock/v1/quotations/search-info` | `CTPF1002R` | `shtn_pdno` |
| name (by name) | Same | Same | `prdt_name` |
| market | Same | Same | `mket_id_cd` (mapped to KOSPI/KOSDAQ) |

KIS market code mapping:

| `mket_id_cd` | Canonical |
|--------------|-----------|
| `STK`, `KSP` | `KOSPI` |
| `KSQ`, `KDQ`, `KNX` | `KOSDAQ` |
| (other / unknown) | Falls back to `KOSPI` |

## 2. Error Handling

| Scenario | HTTP Status | Code | Description |
|----------|-------------|------|-------------|
| Empty query | 400 | `INVALID_QUERY` | Search query must not be empty |
| `limit` out of range | 422 | — | FastAPI query validation |
| KIS credentials missing | 503 | `KIS_NOT_CONFIGURED` | Core KIS credentials not set |
| KIS API failure | 200 | — | Logged and returned as empty result (not an error surface) |

## 3. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Stocks endpoints | `app/api/v1/stocks.py` | api |
| Stocks service | `app/services/stocks.py` | services |
| Stock master index | `app/services/stock_index.py` | services |
| KIS master parsers | `app/kis/master.py` | kis |
| KIS client | `app/kis/client.py` | kis |
| KIS response models | `app/kis/models.py` | kis |

## 4. Phase 2 Extensions (placeholder, not implemented)

- `GET /api/v1/stocks/{symbol}` — Single-stock detail (current price, volume, 52-week range, fundamentals)
- `GET /api/v1/stocks/{symbol}/history?period=1m` — Historical OHLCV series
- `GET /api/v1/stocks/{symbol}/news` — News sentiment feed
- Background daemon that refreshes the Local Master Index on a schedule instead of only at startup
- Halted / delisted filtering driven by the Part 2 suspension flags in the KR master files
- Conditional GET (`If-Modified-Since`) against the master-file CDN so the daily refresh is a no-op on unchanged days
