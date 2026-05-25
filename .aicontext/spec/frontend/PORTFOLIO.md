# Portfolio Spec

Holdings-focused page that shows the user's current positions, aggregate
asset allocation, and the same account summary card used on the Dashboard.

Route: `/portfolio`

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header (global Header with nav tabs)          │
├─────────────────────────────────────────────────┤
│  Account Summary (shared with Dashboard)        │
├─────────────────────────────────────────────────┤
│  Asset Allocation (stacked-bar + legend)       │
├─────────────────────────────────────────────────┤
│  Holdings table (sortable)                      │
└─────────────────────────────────────────────────┘
```

Sections are stacked full-width on every breakpoint. The holdings table
becomes horizontally scrollable on narrow viewports (`overflow-x-auto`).

## 1. Account Summary section

Reuses `AccountSummary` from `app/dashboard/_components/`. Same polling,
same coexistence pattern, same query key `['portfolio', 'summary']`.

## 2. Asset Allocation

Stacked horizontal bar + legend. Computes each holding's weight as
`evaluationAmount / total(evaluationAmount)`, sorts by weight descending,
and renders a segmented bar plus a legend listing symbol, percentage, and
evaluated value.

Phase 1.5-compatible visual language: brand teal primary, gray fills for
long-tail weights. No external charting library — pure Tailwind. A proper
donut chart can replace `AllocationChart` in a later slice without
touching the data flow.

### API

- `GET /api/v1/portfolio/holdings` → `HoldingsResult`

### Query key

`['portfolio', 'holdings']` (shared with the Holdings table via the
`usePortfolioHoldings` hook).

## 3. Holdings table

### Columns

| Column | Source | Format |
|--------|--------|--------|
| Name / Symbol | `holding.name` / `holding.symbol` | name + monospace symbol below |
| Qty | `holding.quantity` | `formatVolume` (ko-KR grouping) |
| Avg | `holding.avgPurchasePrice` | `formatKrw` |
| Current | `holding.currentPrice` | `formatKrw` |
| Value | `holding.evaluationAmount` | `formatKrw` (bold) |
| P&L | `holding.profit` + `holding.profitRate` | `ChangeDisplay` (amount + rate, color-coded) |

### Sorting

Click a sortable column header to toggle sort direction. Sort keys:
`name`, `profitRate`, `evaluationAmount`. Default: `evaluationAmount` desc.
Non-sortable columns (Qty/Avg/Current) render the label without a click
handler.

### Degraded rows

When KIS price lookup fails for a held symbol, the backend returns the
position under `errors[]` with quantity + avg purchase price preserved.
`DegradedHoldingRow` renders these pinned at the bottom of the table with
amber background, `—` for current/value, and `Lookup failed` caption.
`aria-live="polite"` on the row without a role override (jsx-a11y rejects
explicit `role="status"` on `<tr>` since rows have an implicit `row` role).

### Empty state

When both `holdings` and `errors` are empty the table shows a Korean-text
empty state that directs the user to the Trading page.

## 4. Types

```typescript
interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avgPurchasePrice: number;
  currentPrice: number;
  evaluationAmount: number;
  purchaseAmount: number;
  profit: number;
  profitRate: number;
}

interface HoldingError {
  symbol: string;
  name: string;
  quantity: number;
  avgPurchasePrice: number;
  purchaseAmount: number;
  errorCode: string;
  message: string;
}

interface HoldingsResult {
  holdings: Holding[];
  errors: HoldingError[];
}
```

Both types live in `src/types/portfolio.ts`.

## 5. Components

Page-local in `src/app/portfolio/_components/`:

| Component | Description |
|-----------|-------------|
| `HoldingsSection` | Card wrapper, loading/error/stale UI, sort state |
| `HoldingsTable` | Table with sortable headers |
| `HoldingRow` | Single holding row |
| `DegradedHoldingRow` | Degraded row for failed KIS lookups |
| `AllocationSection` | Card wrapper + loading/error/stale UI |
| `AllocationChart` | Stacked-bar + legend from Holding[] |

Hook: `src/app/portfolio/_hooks/usePortfolioHoldings.ts` — wraps
`useQuery` + `useMarketPollingInterval` so both the allocation chart and
the holdings table share a single cached query.

## 6. State Management

| Data | Type | Tool | Key |
|------|------|------|-----|
| Account summary | Server | TanStack Query | `['portfolio', 'summary']` |
| Holdings | Server | TanStack Query | `['portfolio', 'holdings']` |
| Sort key/order | Local | `useState` | — |

Polling: 30 s during KST market hours, disabled otherwise. Shared via
`useMarketPollingInterval` from `src/hooks/`.

## 7. API integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/portfolio/summary` | GET | Cash + total asset + daily P&L |
| `/api/v1/portfolio/holdings` | GET | Per-symbol positions with envelope `{holdings, errors, count}` |
