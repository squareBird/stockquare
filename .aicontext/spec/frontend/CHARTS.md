# Charts Spec

Price charts shown two ways, both built on the same `SymbolChart` core
(candlestick + volume rendered with TradingView's **lightweight-charts**):

1. **Stock detail modal** — opens when the user clicks a symbol on the
   **Dashboard** or **Portfolio**. The modal — not a dedicated route — layers
   charting on top of those pages without adding a nav tab.
2. **Inline panel on the Trading page** — the Trading page does **not** use the
   modal. Selecting a symbol (from the left-rail watchlist or the search
   results) renders the chart inline in the main column, alongside the order
   entry, so the user can chart and trade without a popup.

Both surfaces share the `SymbolChart` component (header price line + interval
toggle + chart, with the KR-only / overseas-degradation rules in §2).

> **Data prerequisite**: this depends on `GET /api/v1/stocks/{symbol}/history`,
> currently a Phase 2 placeholder in backend `STOCKS.md`. That endpoint (the
> same OHLCV source the Strategy engine uses — see backend `STRATEGY.md` §6)
> must exist before charts can render real data. Until then `PriceChart`
> renders against the mock adapter in `lib/api/mock.ts`.

## Entry points

**Modal (Dashboard / Portfolio)** — a single global modal, driven by a Zustand
store holding the `activeSymbol`. These click targets call
`openStockDetail(symbol, name)`:

- Dashboard `WatchlistItem` (and `DegradedWatchlistItem`)
- `AddStockModal` search result row (name region; the trailing button still adds)
- Portfolio `HoldingRow`

The modal is mounted once near the root (`providers.tsx`) so it is reachable
from those pages.

**Inline (Trading)** — the Trading page selects a symbol into local state
instead of opening the modal. Both the left-rail `TradingWatchlist` rows and the
`SymbolPicker` search results call the page's `onSelect`, which sets the symbol
that drives the inline `SymbolChart` **and** arms the order entry. `SymbolPicker`
therefore does not open the modal.

## Layout (modal)

```
┌───────────────────────────────────────────────┐
│  삼성전자  005930 · KOSPI            [Close]  │  header
│  ₩72,000   ▲ +1,200 (+1.69%)                 │  current price (ChangeDisplay)
├───────────────────────────────────────────────┤
│  [분봉] [일봉] [주봉] [월봉]                   │  interval toggle
├───────────────────────────────────────────────┤
│                                                │
│            candlestick series                  │  PriceChart
│            ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄                  │
│            volume histogram                    │
│                                                │
├───────────────────────────────────────────────┤
│  [관심종목 추가]            [주문하기 →]       │  quick actions
└───────────────────────────────────────────────┘
```

Bottom sheet on mobile (`items-end`, `rounded-t-2xl`), centered dialog on
`md:` and up — same responsive shell as `AddStockModal`.

## 1. StockDetailModal

The container. Follows the exact a11y pattern already used by
`AddStockModal`:

- `role="dialog"`, `aria-modal="true"`, `aria-label` with the symbol.
- Backdrop is a `<button tabIndex={-1} aria-hidden="true">`; pointer users
  dismiss by clicking it, keyboard users via Escape or the visible Close
  button.
- Closing clears `activeSymbol` in the store.

Sections: header (name + symbol + market + live price), interval toggle,
`PriceChart`, and a quick-actions row. The header price reuses
`PriceDisplay` + `ChangeDisplay` from `components/common/` and shares the
`['stocks', symbol, 'price']` query with the rest of the app.

## 2. PriceChart (lightweight-charts)

Wraps a `lightweight-charts` chart instance.

- **Candlestick series** for OHLC + a **volume histogram** on a secondary
  price scale.
- **Korean color convention** (matches the app's `gain` / `loss` tokens):
  up candles **red**, down candles **blue**. lightweight-charts defaults to
  green/red, so `upColor` / `downColor` / `wickUpColor` / `wickDownColor`
  must be set explicitly to the brand red/blue. Volume bars tint with the
  same up/down color at reduced opacity.
- `'use client'`, and the chart module is loaded via `next/dynamic` with
  `ssr: false` (lightweight-charts touches `window`/`document` on import).
- A `ResizeObserver` keeps the chart width in sync with the container, and
  **re-fits the visible range on every resize** (`timeScale().fitContent()`)
  so the full candle series stays in view — narrowing the panel must never
  push the oldest candles off the left edge. The time scale also fixes both
  edges to the data bounds (`fixLeftEdge` / `fixRightEdge`) so the user can
  zoom within the series but cannot scroll past it into empty space and lose
  the earlier candles. The chart instance is created in a `useEffect` and
  `remove()`d on cleanup to avoid leaks across symbol switches.
- Loading / error / empty states mirror the card pattern used elsewhere:
  skeleton while fetching, a stale badge if cached data is shown during a
  refetch, and a Korean "차트 데이터를 불러올 수 없습니다" message on full
  failure.
- **KR-only (Phase 1).** Charting, watchlist, and trading use domestic KIS
  endpoints (KRW), so they accept 6-digit KRX codes only. Overseas symbols are
  searchable for discovery but `SymbolChart` skips the history fetch for a
  non-`^\d{6}$` symbol and shows "해외 종목 차트는 아직 지원하지 않습니다"; the
  modal's quick actions are likewise disabled for overseas symbols. Full
  overseas price/chart support is deferred (see backend `STOCKS.md` Phase 2).

## 3. Interval selector

A small pill toggle selecting **candle granularity** (not a lookback window).
Each interval maps to a backend `interval` value; the backend derives the
visible range and source endpoint (see `STOCKS.md` §2):

| Pill | `interval` param | Granularity | Visible window | Source tr_id (backend) |
|------|------------------|-------------|----------------|------------------------|
| 분봉 | `min`   | 1-minute (intraday) | current session | `FHKST03010200` |
| 일봉 | `day`   | daily   | ~6 months | `FHKST03010100` |
| 주봉 | `week`  | weekly  | ~2 years  | `FHKST03010100` |
| 월봉 | `month` | monthly | ~5 years  | `FHKST03010100` |

Default `day`. Switching intervals changes the query key, so each interval's
data is cached independently. `SymbolChart` accepts an optional
`initialInterval` so the AI assistant can open the chart at a requested
granularity (`/trading?symbol=&name=&interval=`).

## 4. Data / API integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/stocks/{symbol}/history?interval=` | GET | OHLCV candle series for the chart |
| `/api/v1/stocks/{symbol}/price` (or `/auth`-shared price) | GET | Header current price + change |

History response (formalized in `STOCKS.md` §2):
```json
{
  "symbol": "005930",
  "interval": "day",
  "candles": [
    { "time": "2026-05-02", "open": 71000, "high": 72500, "low": 70800, "close": 72000, "volume": 12345678 }
  ]
}
```

`time` is an ISO date for day/week/month candles, or epoch seconds (int) for
`min` candles. Query key: `['stocks', symbol, 'history', interval]`. Polling:
during KRX market hours the chart may refetch the latest candle on the shared
`useMarketPollingInterval` (Phase 2); Phase 1 fetches once per open.

## 5. Types

```typescript
type ChartInterval = 'min' | 'day' | 'week' | 'month';

// lightweight-charts expects `time` as 'yyyy-mm-dd' (day/week/month) or a UNIX
// timestamp in seconds (intraday min); the backend already emits the right form.
interface Candle {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface StockHistoryResult {
  symbol: string;
  interval: ChartInterval;
  candles: Candle[];
}
```

Live in `src/types/charts.ts`. The adapter that maps the backend payload to
lightweight-charts series data lives in `lib/api/adapters.ts` alongside the
existing adapters.

## 6. Components

| Component | Location | Description |
|-----------|----------|-------------|
| `SymbolChart` | `src/components/common/` | Shared header price + interval toggle + chart; KR-only / overseas degradation. Used by both surfaces |
| `StockDetailModal` | `src/components/common/` | Global modal shell (Dashboard/Portfolio): wraps `SymbolChart` + quick actions + a11y |
| `PriceChart` | `src/components/common/` | lightweight-charts candlestick + volume |
| `IntervalToggle` | `src/components/common/` | Candle-interval pill group (분/일/주/월) |
| `TradingWatchlist` | `src/app/trading/_components/` | Trading-page left-rail watchlist; rows select the symbol for the inline chart + order |

These are shared (cross-page) components, so they live under
`components/common/` rather than a page-local `_components/` folder, consistent
with `PriceDisplay` / `ChangeDisplay` / `StaleBadge`.

## 7. State Management

| Data | Type | Tool | Key / Scope |
|------|------|------|-------------|
| Active symbol (open modal) | Client | Zustand | `useStockDetail` store (`activeSymbol`, `open`, `close`) |
| Candle history | Server | TanStack Query | `['stocks', symbol, 'history', interval]` |
| Header price | Server | TanStack Query | `['stocks', symbol, 'price']` |
| Selected interval | Local | `useState` | `SymbolChart` |

The Zustand store mirrors the shape in the project's `STATE_MANAGEMENT.md`
example (a `selectedSymbol`-style modal store): a nullable symbol plus
`open(symbol)` / `close()` actions.

## 8. Library / Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `lightweight-charts` | Candlestick + volume rendering | Loaded via `next/dynamic` (`ssr: false`); the only new frontend dependency. |

The Portfolio `AllocationChart` stays as-is — it is a pure-Tailwind allocation
bar, not a price chart, and does not adopt lightweight-charts.

## 9. Phasing & Extensions

- **Phase 1** — Modal + daily candlestick (1W/1M/3M/1Y) with volume, against
  the backend history endpoint (or mock until it lands). Red/blue convention,
  responsive, a11y.
- **Phase 2** — Intraday 1D minute candles, indicator overlays (MA, Bollinger
  bands — the same indicators the Strategy engine computes), and live
  last-candle updates during market hours.
- **Later** — WebSocket-driven realtime candles (`feat/realtime-chart`),
  drawing tools, and comparison overlays.
