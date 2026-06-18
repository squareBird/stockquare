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

## 2. Stock Price History

Daily OHLCV series that backs the frontend price chart (`CHARTS.md`) and the
strategy engine's indicator math (`STRATEGY.md` §6). One KIS call per request;
no caching in Phase 1.

### GET /api/v1/stocks/{symbol}/history

**Path / Query Parameters**:
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `symbol` (path) | string | Yes | — | 6-digit KRX code |
| `period` (query) | enum | No | `1m` | One of `1w`, `1m`, `3m`, `1y` |

`period` maps to a lookback window (counted back from today in KST) and the KIS
period-division code:

| `period` | Window | `FID_PERIOD_DIV_CODE` |
|----------|--------|-----------------------|
| `1w` | 7 days | `D` |
| `1m` | 1 month | `D` |
| `3m` | 3 months | `D` |
| `1y` | 1 year | `D` |

Intraday minute candles (`1d`) are deferred to Phase 2 (KIS
`inquire-time-itemchartprice`, `FHKST03010200`).

**Response**:
```json
{
  "symbol": "005930",
  "period": "1m",
  "candles": [
    { "time": "2026-05-02", "open": 71000, "high": 72500, "low": 70800, "close": 72000, "volume": 12345678 }
  ]
}
```

Candles are ordered **oldest → newest**. `time` is an ISO date (`YYYY-MM-DD`)
for daily candles. lightweight-charts consumes this directly.

**Response Model**:
```python
class ChartPeriod(str, Enum):
    ONE_WEEK = "1w"
    ONE_MONTH = "1m"
    THREE_MONTH = "3m"
    ONE_YEAR = "1y"

class Candle(BaseModel):
    time: str        # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int

class StockHistoryResponse(BaseModel):
    symbol: str
    period: ChartPeriod
    candles: list[Candle]
```

### Behavior

- Candles come from `inquire-daily-itemchartprice`. KIS returns rows
  newest-first; the service reverses them to oldest → newest.
- Invalid 6-digit symbol (KIS `rt_cd != "0"`) → 400 `INVALID_SYMBOL`.
- No rows in the window → 200 with `"candles": []` (not an error surface).

### KIS API Mapping

| Field | KIS Endpoint | tr_id | KIS Field |
|-------|-------------|-------|-----------|
| time | `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | `FHKST03010100` | `stck_bsop_date` |
| open | Same | Same | `stck_oprc` |
| high | Same | Same | `stck_hgpr` |
| low | Same | Same | `stck_lwpr` |
| close | Same | Same | `stck_clpr` |
| volume | Same | Same | `acml_vol` |

### KIS Request Details

```
GET {base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
Headers:
  authorization: Bearer {token}
  appkey / appsecret / custtype: P
  tr_id: FHKST03010100
Query:
  FID_COND_MRKT_DIV_CODE: "J"
  FID_INPUT_ISCD: {symbol}
  FID_INPUT_DATE_1: {from YYYYMMDD}
  FID_INPUT_DATE_2: {to YYYYMMDD}
  FID_PERIOD_DIV_CODE: "D"
  FID_ORG_ADJ_PRC: "0"   # 0 = adjusted (수정주가) price series
```

Daily candles come back in the `output2` array.

> **tr_id verification note**: `FHKST03010100` is the commonly-documented
> daily-chart tr_id but, like the trading tr_ids in `TRADING.md`, it must be
> verified against `koreainvestment/open-trading-api` (`examples_llm/`,
> `legacy/rest/`) before merge. Any mismatch surfaces as `rt_cd != "0"` and is
> captured by `_log_kis_error_body`.

## 3. Error Handling

| Scenario | HTTP Status | Code | Description |
|----------|-------------|------|-------------|
| Empty query | 400 | `INVALID_QUERY` | Search query must not be empty |
| `limit` out of range | 422 | — | FastAPI query validation |
| Invalid `period` | 422 | — | FastAPI query validation against the enum |
| History symbol not found | 400 | `INVALID_SYMBOL` | KIS `rt_cd != "0"` for the requested code |
| KIS credentials missing | 503 | `KIS_NOT_CONFIGURED` | Core KIS credentials not set |
| Search KIS API failure | 200 | — | Logged and returned as empty result (not an error surface) |
| History KIS API failure | 502 | `KIS_API_ERROR` | Upstream chart-price failure (history is not silently emptied) |

## 4. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Stocks endpoints | `app/api/v1/stocks.py` | api |
| Stocks service | `app/services/stocks.py` | services |
| Stock master index | `app/services/stock_index.py` | services |
| KIS master parsers | `app/kis/master.py` | kis |
| KIS client | `app/kis/client.py` | kis |
| KIS response models | `app/kis/models.py` | kis |

## 5. Phase 2 Extensions (placeholder, not implemented)

- `GET /api/v1/stocks/{symbol}` — Single-stock detail (current price, volume, 52-week range, fundamentals)
- `GET /api/v1/stocks/{symbol}/history?period=1d` — Intraday **minute** candles (`inquire-time-itemchartprice`, `FHKST03010200`)
- `GET /api/v1/stocks/{symbol}/news` — News sentiment feed
- Background daemon that refreshes the Local Master Index on a schedule instead of only at startup
- Halted / delisted filtering driven by the Part 2 suspension flags in the KR master files
- Conditional GET (`If-Modified-Since`) against the master-file CDN so the daily refresh is a no-op on unchanged days
