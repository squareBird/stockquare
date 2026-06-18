# Strategy Spec

Auto-trading strategy engine. The user defines strategies that are evaluated
against live market data during KRX hours, produce buy/sell/hold **signals**,
and — when explicitly enabled — turn those signals into real orders. Signals
are generated with a **hybrid** of deterministic rule-based technical
indicators and AI (LLM) analysis. Every auto-placed order passes through the
existing Trading safety gates **plus** a dedicated Strategy gate stack before
it reaches KIS, so automated execution can never bypass the manual-trading
guardrails.

> This spec depends on an OHLCV history capability that is currently a Phase 2
> placeholder in `STOCKS.md` (`GET /api/v1/stocks/{symbol}/history`). The
> indicator math and the AI context both consume that series, so the OHLCV
> fetch (Section 6) is a prerequisite for any strategy implementation.

## 0. Concepts

| Term | Meaning |
|------|---------|
| **Strategy** | A persisted, user-defined rule set: target symbol, signal method, parameters, order sizing, and execution mode. |
| **Evaluation** | A single run of a strategy against the latest OHLCV + indicators that yields one signal. |
| **Signal** | The evaluation output: `action` ∈ {`buy`, `sell`, `hold`}, plus confidence and rationale. Persisted for history/audit. |
| **Execution** | Converting a non-`hold` signal into an order through the existing `trading` service. Gated (Section 5). |

## 1. Endpoints

All strategy endpoints live under `/api/v1/strategies`.

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/api/v1/strategies` | Create a strategy definition |
| GET    | `/api/v1/strategies` | List all strategies with their latest signal |
| GET    | `/api/v1/strategies/{id}` | Fetch a single strategy |
| PATCH  | `/api/v1/strategies/{id}` | Update parameters / toggle `active` / change `execution_mode` |
| DELETE | `/api/v1/strategies/{id}` | Delete a strategy and its signal history |
| POST   | `/api/v1/strategies/{id}/evaluate` | Evaluate now and return the signal **without** placing an order (dry-run) |
| GET    | `/api/v1/strategies/{id}/signals` | Signal history for the strategy (most recent first) |

`POST /{id}/evaluate` is the safe, always-available manual trigger: it never
executes, regardless of `execution_mode`. Auto-execution only happens through
the background scheduler (Section 4) when all gates pass.

## 2. Strategy Definition

### Create strategy
```json
POST /api/v1/strategies
{
  "name": "삼성전자 골든크로스",
  "symbol": "005930",
  "strategy_type": "hybrid",
  "execution_mode": "signal_only",
  "side_policy": "long_only",
  "rule": {
    "indicators": [
      { "kind": "ma_cross", "fast": 5, "slow": 20 },
      { "kind": "rsi", "period": 14, "oversold": 30, "overbought": 70 }
    ]
  },
  "ai": {
    "enabled": true,
    "model": "claude-haiku-4-5-20251001",
    "role": "confirm"
  },
  "sizing": { "mode": "fixed_amount", "amount_krw": 50000 },
  "active": false
}
```

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | Human label, ≤ 100 chars |
| `symbol` | str | 6-digit KRX code; verified via the stocks index on create |
| `strategy_type` | enum | `rule` \| `ai` \| `hybrid` |
| `execution_mode` | enum | `signal_only` (never orders) \| `auto` (orders when gated-on) |
| `side_policy` | enum | `long_only` (buy, then sell own position) \| `both` |
| `rule.indicators` | list | Rule definitions; required when `strategy_type` ∈ {`rule`, `hybrid`} |
| `ai` | object | Required when `strategy_type` ∈ {`ai`, `hybrid`}; `role` ∈ {`confirm`, `decide`} |
| `sizing.mode` | enum | `fixed_quantity` (`quantity`) \| `fixed_amount` (`amount_krw`) |
| `active` | bool | Whether the scheduler evaluates it; defaults `false` |

### Response (`201 Created`)
```json
{
  "id": 12,
  "name": "삼성전자 골든크로스",
  "symbol": "005930",
  "name_kr": "삼성전자",
  "strategy_type": "hybrid",
  "execution_mode": "signal_only",
  "side_policy": "long_only",
  "rule": { "indicators": [ ... ] },
  "ai": { "enabled": true, "model": "claude-haiku-4-5-20251001", "role": "confirm" },
  "sizing": { "mode": "fixed_amount", "amount_krw": 50000 },
  "active": false,
  "created_at": "2026-05-25T09:30:14+00:00",
  "last_signal": null
}
```

### Response Model
```python
class StrategyType(str, Enum):
    RULE = "rule"
    AI = "ai"
    HYBRID = "hybrid"

class ExecutionMode(str, Enum):
    SIGNAL_ONLY = "signal_only"
    AUTO = "auto"

class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class StrategyResponse(BaseModel):
    id: int
    name: str
    symbol: str
    name_kr: str                  # resolved from the stocks index
    strategy_type: StrategyType
    execution_mode: ExecutionMode
    side_policy: str
    rule: RuleConfig | None
    ai: AIConfig | None
    sizing: SizingConfig
    active: bool
    created_at: datetime
    last_signal: SignalResponse | None

class StrategiesResponse(BaseModel):
    strategies: list[StrategyResponse]
    count: int
```

## 3. Signal Generation

### 3.1 Rule-based signals
Computed deterministically from the OHLCV series (Section 6). Phase-1 indicators:

| `kind` | Parameters | Buy when | Sell when |
|--------|-----------|----------|-----------|
| `ma_cross` | `fast`, `slow` | fast MA crosses **above** slow (golden cross) | fast MA crosses **below** slow (dead cross) |
| `rsi` | `period`, `oversold`, `overbought` | RSI crosses up through `oversold` | RSI crosses down through `overbought` |
| `bollinger` | `period`, `mult` | close touches/penetrates lower band | close touches/penetrates upper band |

Multiple indicators are combined with **unanimity**: a `buy` requires every
indicator to agree on `buy`; same for `sell`; otherwise `hold`. (Phase 2 may
add weighted / any-of combinators.)

### 3.2 AI signals
The AI advisor receives a compact, bounded context — the last N candles, the
current indicator snapshot, and the held position — and returns a structured
verdict. Built with the Anthropic SDK; prompt caching is applied to the static
system instructions.

```python
class AISignal(BaseModel):
    action: SignalAction
    confidence: float    # 0.0–1.0
    rationale: str       # short, bounded; surfaced in signal history
```

Model output is parsed via structured / tool output (no free-text scraping).
On any AI error or timeout the signal degrades to `hold` with an
`ai_unavailable` rationale — the engine never fails open into a trade.

### 3.3 Hybrid resolution
For `strategy_type=hybrid` the rule produces a candidate, then AI is applied per
its `role`:

| AI `role` | Final action |
|-----------|--------------|
| `confirm` | Execute the rule's candidate only if AI agrees on the same non-`hold` action; otherwise `hold`. |
| `decide` | Rule candidate is advisory context; AI's `action` is final. |

## 4. Evaluation & Scheduling

- **Manual** (`POST /{id}/evaluate`): evaluate one strategy on demand, return
  the signal, never execute. Available in Phase 1.
- **Scheduled** (Phase 2): a background loop evaluates every `active` strategy
  on its interval, but **only during KRX regular hours** (09:00–15:30 KST,
  Mon–Fri — same window as `MARKET.md`). Outside the window the scheduler is
  idle. Each scheduled evaluation persists a signal and, if all gates pass,
  triggers execution (Section 5).

Default evaluation interval: 60 s per strategy (configurable later). The
scheduler runs inside the FastAPI app lifespan and is cancelled on shutdown.

## 5. Auto-Execution & Safety Gates

A non-`hold` signal becomes an order **only** when the full gate stack passes.
Strategy orders are placed through the existing `trading` service, so they
inherit its gates — the Strategy gates are layered **on top**, never instead of.

Gate stack (evaluated in order; first failure short-circuits to "no order"):

1. **`execution_mode == "auto"`** — per-strategy opt-in. `signal_only` always stops here.
2. **`STRATEGY_AUTO_EXECUTE_ENABLED`** (env, default `false`) — global kill
   switch. When `false`, every strategy is effectively downgraded to
   `signal_only` regardless of its own setting.
3. **`STRATEGY_MAX_ORDER_AMOUNT`** (env, default `50_000` KRW) — per-order cap
   specific to automated orders; intended to be ≤ `TRADING_MAX_ORDER_AMOUNT`.
4. **`STRATEGY_MAX_DAILY_ORDERS`** (env, default `5`) — per-strategy daily
   execution count cap (KST day). Exceeding it suppresses execution and records
   a `daily_limit_reached` signal note.
5. **Trading service gates** — the order then passes through
   `TRADING_REAL_MODE_ENABLED` and `TRADING_MAX_ORDER_AMOUNT` exactly as a
   manual order would.

### Real auto-execution decision matrix

| `KIS_ACCOUNT_MODE` | `STRATEGY_AUTO_EXECUTE_ENABLED` | `TRADING_REAL_MODE_ENABLED` | Result |
|--------------------|---------------------------------|-----------------------------|--------|
| `mock` | `true` | (n/a) | Auto-orders on the **mock** account |
| `real` | `false` | any | **Signal only** — no real order |
| `real` | `true` | `false` | Blocked by `TradingDisabledError` (403) |
| `real` | `true` | `true` | **Live auto-order** on the real account |

Real-money automated trading therefore requires `KIS_ACCOUNT_MODE=real` **and**
both flags `true` — three independent switches, none defaulting to "on".

### Structured logging
Every auto-execution attempt is logged like a manual order (`WARNING` in real
mode, `INFO` in mock) with `extra` fields: `strategy_id`, `action`,
`account_mode`, `symbol`, `quantity`, `price`, `amount`, and the resulting
`order_id`. The signal that triggered it is logged with its `rationale`.
Credentials are never logged.

## 6. KIS API Mapping (OHLCV source)

Indicators and AI context both need a candle series. Two KIS quotation calls
cover the Phase-1 (daily) and Phase-2 (minute) needs:

| Series | Endpoint | tr_id | Key fields |
|--------|----------|-------|-----------|
| Daily / weekly / monthly | `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | `FHKST03010100` | `stck_bsop_date`, `stck_oprc`, `stck_hgpr`, `stck_lwpr`, `stck_clpr`, `acml_vol` |
| Minute (intraday) | `/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice` | `FHKST03010200` | `stck_cntg_hour`, OHLC, `cntg_vol` |

> **tr_id verification note**: `FHKST03010100` / `FHKST03010200` are the
> commonly-documented chart-price tr_ids but, like the trading tr_ids in
> `TRADING.md`, they must be verified against `koreainvestment/open-trading-api`
> (`examples_llm/`, `legacy/rest/`) before merge. Any mismatch surfaces as
> `rt_cd != "0"` and is captured by `_log_kis_error_body`.

The OHLCV fetch is shared with the frontend `CHARTS.md` and should land in
`STOCKS.md` as `GET /api/v1/stocks/{symbol}/history` so both consumers reuse one
service path rather than each calling KIS directly.

## 7. Data Model (DB)

```python
class Strategy(Base):
    __tablename__ = "strategy"
    id: Mapped[int]              # PK, autoincrement
    name: Mapped[str]            # String(100)
    symbol: Mapped[str]          # String(6), indexed
    strategy_type: Mapped[str]   # String(16)
    execution_mode: Mapped[str]  # String(16)
    side_policy: Mapped[str]     # String(16)
    config: Mapped[dict]         # JSON: { rule, ai, sizing }
    active: Mapped[bool]         # indexed; scheduler filters on this
    created_at: Mapped[datetime] # server_default=func.now()

class StrategySignal(Base):
    __tablename__ = "strategy_signal"
    id: Mapped[int]              # PK
    strategy_id: Mapped[int]     # FK → strategy.id, indexed
    action: Mapped[str]          # String(8): buy/sell/hold
    confidence: Mapped[float]
    rationale: Mapped[str]       # Text
    executed: Mapped[bool]       # whether it produced an order
    order_id: Mapped[str | None] # composite KIS order id when executed
    created_at: Mapped[datetime]
```

Composite indicator / AI / sizing config is stored as a single JSON column to
keep the schema stable as new indicator kinds are added.

## 8. Error Handling

| Scenario | HTTP | Code |
|----------|------|------|
| Pydantic validation (bad symbol / unknown indicator / bad enum) | 422 | — |
| Symbol not found in stocks index | 400 | `INVALID_SYMBOL` |
| Strategy id not found | 404 | `STRATEGY_NOT_FOUND` |
| AI advisor failed / timed out (during evaluate) | 200 | — (signal degrades to `hold`, `ai_unavailable` note) |
| Auto-execution blocked by a Strategy gate | — | no order; recorded as a signal note, not an HTTP error |
| Auto-execution blocked by trading gate (real mode off) | 403 | `TRADING_DISABLED` (propagated from trading) |
| Order rejected by KIS | 400 | `ORDER_FAILED` (propagated from trading) |
| KIS credentials missing | 503 | `KIS_NOT_CONFIGURED` |
| KIS API failure | 502 | `KIS_API_ERROR` |

New exceptions live in `app/core/exceptions.py` following the `ClassVar`
pattern: `StrategyNotFoundError` (404 / `STRATEGY_NOT_FOUND`).

## 9. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Strategy endpoints | `app/api/v1/strategy.py` | api |
| Strategy service (CRUD, evaluate, execute) | `app/services/strategy.py` | services |
| Indicator math | `app/services/indicators.py` | services |
| AI advisor | `app/services/strategy_ai.py` | services |
| Order placement (reused) | `app/services/trading.py` | services |
| OHLCV fetch (reused) | `app/services/stocks.py` + `app/kis/client.py` | services / kis |
| Domain models | `app/models/strategy.py` | models |
| ORM models | `app/db/models.py` (`Strategy`, `StrategySignal`) | db |
| Exceptions | `app/core/exceptions.py` (`StrategyNotFoundError`) | core |
| Settings | `app/core/config.py` (`strategy_auto_execute_enabled`, `strategy_max_order_amount`, `strategy_max_daily_orders`) | core |

`api/` calls `services/strategy.py` only; the strategy service orchestrates
indicators, AI, OHLCV, and the trading service — it never calls `kis/` for
order placement directly (dependency rule in `PROJECT_STRUCTURE.md`).

## 10. New Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `pandas` (or pure-Python equivalents) | MA / RSI / Bollinger math | A small hand-rolled module is acceptable for Phase 1 to avoid the heavy dep; revisit if the indicator count grows. |
| `anthropic` | AI signal advisor | Required only for `ai` / `hybrid` strategies; apply prompt caching to the system prompt. |

A scheduler (asyncio background task in the app lifespan; APScheduler optional)
is needed only for Phase 2 scheduled evaluation.

## 11. Phasing & Extensions

Auto-execution is intentionally rolled out in stages so live money is the last
switch flipped, not the first.

- **Phase 1** — Strategy CRUD, rule-based signals, manual `POST /{id}/evaluate`
  (dry-run only). No scheduler, no auto-execution, no AI. Validates indicator
  math against mocked OHLCV.
- **Phase 2** — Background scheduler (KRX-hours only), AI / hybrid signals, and
  auto-execution **on the mock account first** (`KIS_ACCOUNT_MODE=mock`).
- **Phase 3** — Real-money auto-execution, enabled only via the three-switch
  matrix in Section 5. Add backtesting (`POST /api/v1/strategies/{id}/backtest`
  over a historical OHLCV window) before trusting any strategy with real funds.
- **Later** — Multi-symbol / portfolio strategies, weighted indicator
  combinators, stop-loss / take-profit exits, WebSocket-driven evaluation
  (replacing polling).
