# Strategy Spec (Frontend)

Auto-trading **strategy** management page. The user defines rule-based
strategies against a KR symbol, runs a **manual evaluation** (dry-run), and
reviews the resulting buy/sell/hold **signal** and its history. This is the
frontend for backend `STRATEGY.md`.

Route: `/strategy` (new fourth nav tab, after Portfolio).

> **Scope (Phase 1).** Rule-based strategies + manual dry-run evaluation only.
> No background scheduler, no AI/hybrid signals, no auto-execution, no real
> money. The create form is therefore fixed to `strategy_type = rule` and
> `execution_mode = signal_only`; the `active` toggle and `auto` execution are
> deferred to Phase 2 (scheduler) and shown as disabled/"준비 중" affordances so
> the UI communicates the roadmap without implying live trading. AI/hybrid form
> fields are out of scope here.

## Layout

```
┌─────────────────────────────────────────────────┐
│  Global Header (nav tabs + account status)      │
├─────────────────────────────────────────────────┤
│  Strategy                              [+ 새 전략] │
├───────────────────────┬─────────────────────────┤
│  StrategyList (left)   │  StrategyDetail (right) │
│   ┌─────────────────┐  │   header: name · symbol │
│   │ 삼성전자 GC      │  │   ┌───────────────────┐ │
│   │ 005930 · rule   │  │   │ SignalBadge        │ │
│   │ ● signal_only   │  │   │  HOLD · 방금 평가  │ │
│   │ 최근: HOLD      │  │   └───────────────────┘ │
│   ├─────────────────┤  │   [지금 평가 (드라이런)] │
│   │ SK GC ...       │  │                         │
│   └─────────────────┘  │   규칙: MA(5/20), RSI   │
│                        │   SignalHistory (table) │
└───────────────────────┴─────────────────────────┘
```

Two-column on `md:` and up (list rail + detail), single-column stacked on
mobile (list, then the selected strategy's detail). Selecting a list row sets
the active strategy locally — no modal, mirroring the Trading inline pattern.

## Entry points / nav

- Add a fourth `NavTab` to `components/layout/NavTabs.tsx`:
  `{ href: '/strategy', label: 'Strategy', shortLabel: '전략' }`.
- The page lives at `src/app/strategy/page.tsx` with a client `StrategyWorkspace`
  glue component (same shape as `TradingWorkspace`).

## 1. StrategyList

Left rail listing every strategy (`GET /api/v1/strategies`). Each row shows:

- `name` + resolved `nameKr` / `symbol`
- `strategyType` (Phase 1: always `rule`) and an `executionMode` chip
- the latest signal action (`lastSignal.action`) as a small `SignalBadge`, or
  "평가 전" when `lastSignal` is null

Clicking a row selects it into local state (`selectedId`). Loading / error /
empty states mirror the watchlist card pattern: skeleton rows while fetching,
a Korean error line on full failure, and a "아직 전략이 없습니다. + 새 전략을
눌러 만드세요." empty state.

## 2. StrategyForm (create / edit)

Opens from the header `+ 새 전략` button (create) or a row's edit affordance
(edit). A panel/sheet — **not** the global stock-detail modal — with:

| Field | Control | Notes |
|-------|---------|-------|
| `name` | text | ≤ 100 chars, required |
| `symbol` | `SymbolPicker`-style search | reuse the search; 6-digit KR only (backend verifies via the stocks index) |
| `strategyType` | fixed `rule` | shown read-only in Phase 1 |
| `executionMode` | fixed `signal_only` | `auto` rendered disabled with a "Phase 2" hint |
| `rule.indicators` | indicator builder | add/remove rows; see §3 |
| `sizing` | mode toggle + amount | `fixed_quantity` (quantity) \| `fixed_amount` (amountKrw) |

Submitting calls `POST /api/v1/strategies` (create) or
`PATCH /api/v1/strategies/{id}` (edit), then invalidates `['strategies']`.
422 (bad indicator/enum) and 400 `INVALID_SYMBOL` surface inline.

### Indicator builder

Each indicator row picks a `kind` and its params:

| `kind` | Params (inputs) |
|--------|-----------------|
| `ma_cross` | `fast`, `slow` (ints) |
| `rsi` | `period`, `oversold`, `overbought` |
| `bollinger` | `period`, `mult` |

Multiple indicators combine with **unanimity** (backend rule) — surface a hint:
"모든 지표가 동의해야 매수/매도 신호가 발생합니다." At least one indicator is
required for a `rule` strategy.

## 3. StrategyDetail + manual evaluation

The right pane for the selected strategy:

- **Header**: name, `symbol · nameKr`, `executionMode` chip, edit / delete.
- **Latest signal**: a prominent `SignalBadge` (BUY red / SELL blue / HOLD gray,
  matching the app's gain/loss tokens) with confidence and the relative time.
- **`지금 평가 (드라이런)` button**: calls `POST /api/v1/strategies/{id}/evaluate`.
  This **never places an order** regardless of settings (backend guarantee), so
  it is always safe and always enabled. On success, show the returned signal and
  invalidate `['strategies', id, 'signals']` + `['strategies']` (the list's
  `lastSignal` updates).
- **Rule summary**: a readable render of the configured indicators.
- **SignalHistory**: `GET /api/v1/strategies/{id}/signals` — a table (most recent
  first) of `action`, `confidence`, `rationale`, `createdAt`, and an `executed`
  marker (always false in Phase 1 since dry-run never executes).

Deleting (`DELETE /api/v1/strategies/{id}`) clears the selection and invalidates
`['strategies']`.

## 4. Data / API integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/strategies` | GET | List strategies (+ each `lastSignal`) |
| `/api/v1/strategies` | POST | Create |
| `/api/v1/strategies/{id}` | PATCH | Update |
| `/api/v1/strategies/{id}` | DELETE | Delete |
| `/api/v1/strategies/{id}/evaluate` | POST | Dry-run evaluate → signal (never orders) |
| `/api/v1/strategies/{id}/signals` | GET | Signal history |

API calls live in `lib/api/strategy.ts`; snake_case → camelCase mapping in
`lib/api/adapters.ts` (`toStrategy`, `toSignal`) alongside the existing
adapters. A `lib/api/mock.ts` branch backs the page until the backend lands.

Expected strategy payload (camelCase after adapter):
```json
{
  "id": 12,
  "name": "삼성전자 골든크로스",
  "symbol": "005930",
  "nameKr": "삼성전자",
  "strategyType": "rule",
  "executionMode": "signal_only",
  "sidePolicy": "long_only",
  "rule": { "indicators": [ { "kind": "ma_cross", "fast": 5, "slow": 20 } ] },
  "sizing": { "mode": "fixed_amount", "amountKrw": 50000 },
  "active": false,
  "createdAt": "2026-05-25T09:30:14+00:00",
  "lastSignal": { "action": "hold", "confidence": 0.0, "rationale": "...", "executed": false, "createdAt": "..." }
}
```

## 5. Types

```typescript
type StrategyType = 'rule' | 'ai' | 'hybrid';       // Phase 1 UI: 'rule' only
type ExecutionMode = 'signal_only' | 'auto';        // Phase 1 UI: 'signal_only'
type SignalAction = 'buy' | 'sell' | 'hold';
type IndicatorKind = 'ma_cross' | 'rsi' | 'bollinger';

interface Indicator {
  kind: IndicatorKind;
  // kind-specific params (fast/slow, period/oversold/overbought, period/mult)
  [param: string]: number | string;
}

interface Signal {
  action: SignalAction;
  confidence: number;   // 0.0–1.0
  rationale: string;
  executed: boolean;
  orderId?: string | null;
  createdAt: string;
}

interface Strategy {
  id: number;
  name: string;
  symbol: string;
  nameKr: string;
  strategyType: StrategyType;
  executionMode: ExecutionMode;
  sidePolicy: string;
  rule: { indicators: Indicator[] } | null;
  sizing: { mode: 'fixed_quantity'; quantity: number } | { mode: 'fixed_amount'; amountKrw: number };
  active: boolean;
  createdAt: string;
  lastSignal: Signal | null;
}
```

Live in `src/types/strategy.ts`.

## 6. Components

| Component | Location | Description |
|-----------|----------|-------------|
| `StrategyWorkspace` | `src/app/strategy/_components/` | Glue: holds `selectedId`, wires list + detail + form |
| `StrategyList` | `src/app/strategy/_components/` | Left-rail strategy list, selectable rows |
| `StrategyDetail` | `src/app/strategy/_components/` | Selected strategy: signal, evaluate button, rule summary |
| `StrategyForm` | `src/app/strategy/_components/` | Create/edit panel with the indicator builder |
| `SignalBadge` | `src/components/common/` | BUY/SELL/HOLD pill (gain/loss tokens) — shared, reusable |
| `SignalHistory` | `src/app/strategy/_components/` | Signal history table |

## 7. State Management

| Data | Type | Tool | Key / Scope |
|------|------|------|-------------|
| Strategy list | Server | TanStack Query | `['strategies']` |
| Signal history | Server | TanStack Query | `['strategies', id, 'signals']` |
| Selected strategy | Local | `useState` | `StrategyWorkspace` (`selectedId`) |
| Create/edit form open | Local | `useState` | `StrategyWorkspace` |
| Evaluate / mutate | Server | TanStack Mutation | invalidate `['strategies']` (+ signals) on success |

No polling in Phase 1 (evaluation is manual). Scheduled refetch arrives with the
Phase 2 scheduler.

## 8. Phasing & Extensions

- **Phase 1 (this spec)** — Rule strategies CRUD, manual dry-run evaluate, signal
  history. `signal_only` only; mocked until the backend ships.
- **Phase 2** — `active` toggle + background-scheduler-driven auto-evaluation,
  AI/hybrid form fields and signal rendering, and (gated) `auto` execution with a
  prominent REAL-mode warning reusing the Trading `ModeBanner` language.
- **Later** — Backtesting view (`POST /strategies/{id}/backtest` over a history
  window), multi-symbol/portfolio strategies, and indicator overlays drawn on the
  `SymbolChart` (shared with `CHARTS.md` Phase 2 overlays).
```
