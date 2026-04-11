# Dashboard Spec

Main dashboard page for Stockquare. Displays account summary, watchlist, and market indices at a glance.

Route: `/dashboard`

## Layout

```
┌─────────────────────────────────────────────────┐
│  Header (Account Connection Status)             │
├──────────────────────┬──────────────────────────┤
│  Account Summary     │  Market Index            │
│                      │  (KOSPI / KOSDAQ)        │
├──────────────────────┴──────────────────────────┤
│  Watchlist                                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

- Desktop (≥1024px): 2-column grid for Account Summary + Market Index, full-width Watchlist below.
- Tablet (768–1023px): Same as desktop but with reduced padding.
- Mobile (<768px): Single column, all sections stacked vertically.

## 1. Account Connection Status

Displays the current KIS API account connection state. KIS authentication is handled entirely by the backend; the frontend only reflects status.

### States

| State | Display | Color |
|-------|---------|-------|
| `connected` | "Connected" + account number (masked: `****1234`) | `text-green-500` |
| `disconnected` | "Disconnected" + reconnect message | `text-gray-400` |
| `error` | "Connection Error" + error description | `text-red-500` |

### Component

```
AccountStatus
├── ConnectionIndicator (dot + label)
└── AccountNumber (masked)
```

### API

- `GET /api/v1/auth/status` → `{ status: 'connected' | 'disconnected' | 'error', account_number?: string, message?: string }`

## 2. Account Summary Section

Displays total asset value and daily profit/loss.

### Display Fields

| Field | Backend Field | Description | Format |
|-------|---------------|-------------|--------|
| Total Assets | `total_asset` | Sum of cash + holdings value | `₩1,234,567` (toLocaleString with ₩ prefix) |
| Daily P&L Amount | `daily_profit` | Today's profit or loss | `+₩12,345` / `-₩12,345` |
| Daily P&L Rate | `daily_profit_rate` | Today's P&L as percentage | `+1.23%` / `-1.23%` |
| Cash Balance | `cash_balance` | Available cash for trading | `₩500,000` |
| Holdings Value | `total_asset - cash_balance` (computed) | Total value of stock holdings | `₩734,567` |

### Color Rules

| Condition | Color | Tailwind Class |
|-----------|-------|----------------|
| Positive (> 0) | Red | `text-red-500` |
| Negative (< 0) | Blue | `text-blue-500` |
| Zero (= 0) | Gray | `text-gray-500` |

> Note: Korean stock market convention — red for gain, blue for loss.

### Component

```
AccountSummary
├── TotalAssets (₩ formatted)
├── DailyPnL (amount + rate, color-coded)
├── CashBalance
└── HoldingsValue (computed: total_asset - cash_balance)
```

### Props

```typescript
interface AccountSummaryProps {
  totalAsset: number;
  dailyProfit: number;
  dailyProfitRate: number;
  cashBalance: number;
}
```

`holdingsValue` is computed inside the component as `totalAsset - cashBalance`.

### API

- `GET /api/v1/portfolio/summary` → `AccountSummaryResponse`

### Backend Response Shape

```json
{
  "total_asset": 1234567,
  "daily_profit": 12345,
  "daily_profit_rate": 1.23,
  "cash_balance": 500000
}
```

Frontend uses a thin adapter layer in `lib/api/` to map snake_case backend responses to camelCase TypeScript types before they reach components.

### State

- Server state via TanStack Query.
- Query key: `['portfolio', 'summary']`
- Refetch interval: 30s (market hours only, disabled outside market hours).

## 3. Watchlist Section

User-curated list of stocks to monitor.

### Display Per Stock

| Field | Backend Field | Description | Format |
|-------|---------------|-------------|--------|
| ID | `id` | Watchlist item identifier | number |
| Sort Order | `sort_order` | User-defined order | number |
| Symbol | `symbol` | Stock ticker code | `005930` |
| Name | `name` | Stock name | `Samsung Electronics` |
| Current Price | `price` | Latest price | `₩72,300` |
| Change Amount | `change` | Price change from previous close | `+₩1,200` / `-₩800` |
| Change Rate | `change_rate` | Change as percentage | `+1.69%` / `-1.10%` |
| Volume | `volume` | Today's traded volume | `12,345,678` |

### Color Rules

Same as Account Summary (red = gain, blue = loss, gray = zero).

### Interactions

| Action | Trigger | Behavior |
|--------|---------|----------|
| Add stock | Click "+" button → opens search modal | Search by symbol or name, select to add |
| Remove stock | Hover → "X" button (desktop) / always-visible "X" button (mobile) | Click → remove by `id` (mutation invalidates watchlist query) |
| Sort | Click column header | Toggle: asc → desc → default |
| Row click | — | **Phase 1: Disabled** (Trading page is Phase 2) |

### Sort Options

| Option | Key | Default |
|--------|-----|---------|
| Name (가나다순) | `name` | — |
| Change Rate | `changeRate` | Default (desc) |
| Price | `price` | — |

### Component Tree

```
Watchlist
├── Header row (title + inline StaleBadge + inline sort buttons + inline "+ Add" button)
├── WatchlistItem[]                    # healthy rows
├── Unavailable (N) divider            # shown only when errors[] is non-empty
├── DegradedWatchlistItem[]            # pinned below the sorted healthy list
├── AddStockModal                      # separate file, opened via "+ Add"
└── Empty state ("No stocks yet…")     # rendered when items + errors are both empty
```

The header, sort buttons, add button, and empty state are rendered inline
inside `Watchlist.tsx`. Only `WatchlistItem`, `DegradedWatchlistItem`, and
`AddStockModal` are separate component files.

### Props

```typescript
interface WatchlistItem {
  id: number;
  sortOrder: number;
  symbol: string;
  name: string;
  price: number;
  change: number;
  changeRate: number;
  volume: number;
}

interface WatchlistItemProps {
  item: WatchlistItem;
  onRemove: (id: number) => void;
}

interface AddStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (symbol: string) => void;
}
```

### API

- `GET /api/v1/watchlist` → `{ items: WatchlistItem[], errors: WatchlistItemError[], count: number }`
- `POST /api/v1/watchlist` → Add stock `{ symbol: string }`
- `DELETE /api/v1/watchlist/{item_id}` → Remove stock by `id`
- `PATCH /api/v1/watchlist/reorder` → Reorder `{ ids: number[] }`
- `GET /api/v1/stocks/search?q={query}` → Search stocks for add modal

### Degraded Rows

When a KIS price lookup fails for a watchlisted symbol, the backend still
returns the row — but as a `WatchlistItemError` entry under `errors[]` instead
of a full `WatchlistItem`. The frontend renders these via
`DegradedWatchlistItem`:

- Row keeps the same overall shape so the layout doesn't jump.
- Symbol and error message display in muted amber (`bg-amber-50/40`).
- Price/change areas show `—` with a "Lookup failed" label.
- Remove button still works so the user can evict broken rows.

```typescript
interface WatchlistItemError {
  id: number;
  symbol: string;
  errorCode: string;
  message: string;
}

interface WatchlistResult {
  items: WatchlistItem[];
  errors: WatchlistItemError[];
}
```

`fetchWatchlist()` in `lib/api/watchlist.ts` returns `WatchlistResult`. The
`count` field from the wire envelope is currently discarded after unwrap —
see deferred follow-ups for a future slot-counter UI.

### State

- Watchlist data: Server state via TanStack Query. Query key: `['watchlist']`
- Polling via TanStack Query (30s during market hours).
- Search results: Server state, enabled when `q.length >= 1`. Query key: `['stocks', 'search', q]`
- Sort preference: Client state via Zustand (`useDashboardUI` store).
- Modal open state: Local React state.

## 4. Market Index Section

Displays major Korean market indices (KOSPI, KOSDAQ).

### Display Per Index

| Field | Backend Field | Description | Format |
|-------|---------------|-------------|--------|
| Code | `code` | Index code | `KOSPI` / `KOSDAQ` |
| Name | `name` | Display name | `KOSPI` / `KOSDAQ` |
| Current Value | `value` | Latest index value | `2,687.45` |
| Change Amount | `change` | Change from previous close | `+15.32` / `-8.71` |
| Change Rate | `change_rate` | Change as percentage | `+0.57%` / `-0.32%` |
| Volume | `volume` | Total volume | `1,234,567` |
| Status | `status` | Market status | `open` / `closed` / `pre_market` |

### Color Rules

Same convention (red = gain, blue = loss, gray = zero).

### Component Tree

```
MarketIndex
├── IndexCard (KOSPI)              ← healthy indices
│   ├── IndexName
│   ├── IndexValue
│   └── IndexChange (amount + rate, color-coded)
└── DegradedIndexCard (KOSDAQ)     ← failed indices
    ├── IndexName
    ├── Error Code badge
    └── "Lookup failed" + message
```

### Props

```typescript
interface MarketIndex {
  code: string;
  name: string;
  value: number;
  change: number;
  changeRate: number;
  volume: number;
  status: 'open' | 'closed' | 'pre_market';
}

interface MarketIndexError {
  code: string;
  name: string;
  errorCode: string;
  message: string;
}

interface MarketIndicesResult {
  indices: MarketIndex[];
  errors: MarketIndexError[];
}

interface IndexCardProps {
  index: MarketIndex;
}

interface DegradedIndexCardProps {
  error: MarketIndexError;
}
```

`fetchMarketIndices()` in `lib/api/market.ts` returns `MarketIndicesResult`.

### API

- `GET /api/v1/market/indices` → `{ indices: MarketIndex[], errors: MarketIndexError[] }`

### Degraded Cards

The backend returns a partial-success envelope: healthy indices live in
`indices[]`, and per-index KIS failures live in `errors[]`. The UI renders
`IndexCard` for healthy values and `DegradedIndexCard` (amber background,
warning icon, error message) for failed values. HTTP is still 200 as long
as at least one index succeeds.

### State

- Index data: Server state via TanStack Query. Query key: `['market', 'indices']`
- Polling via TanStack Query (30s during market hours).

## 5. Components Summary

### Page-Local (`app/dashboard/_components/`)

| Component | Type | Description |
|-----------|------|-------------|
| `AccountStatus` | Client | KIS account connection indicator |
| `AccountSummary` | Client | Total assets and daily P&L |
| `Watchlist` | Client | Full watchlist with sort/add/remove |
| `WatchlistItem` | Client | Single stock row in watchlist |
| `DegradedWatchlistItem` | Client | Row for an item whose price lookup failed |
| `AddStockModal` | Client | Search and add stock dialog |
| `IndexCard` | Client | Single market index card (numeric only) |
| `DegradedIndexCard` | Client | Market index card for a failed KIS lookup |
| `MarketIndex` | Client | KOSPI + KOSDAQ index cards |

### Shared (`components/common/`)

| Component | Description |
|-----------|-------------|
| `PriceDisplay` | Formatted price with ₩ prefix |
| `ChangeDisplay` | Change amount + rate with color coding |
| `StaleBadge` | Amber "Stale" chip shown when a refetch fails while cached data is still on screen |

## 6. State Management Summary

| Data | Type | Tool | Query Key / Store |
|------|------|------|-------------------|
| Account status | Server | TanStack Query | `['auth', 'status']` |
| Account summary | Server | TanStack Query | `['portfolio', 'summary']` |
| Watchlist | Server | TanStack Query | `['watchlist']` |
| Stock search | Server | TanStack Query | `['stocks', 'search', q]` |
| Market indices | Server | TanStack Query | `['market', 'indices']` |
| Sort preference | Client | Zustand | `useDashboardUI.sortKey` / `sortOrder` |
| Add modal open | Local | `useState` | — |

### Zustand Store

```typescript
interface DashboardUIState {
  watchlistSortKey: 'name' | 'changeRate' | 'price';
  watchlistSortOrder: 'asc' | 'desc';
  setWatchlistSort: (key: DashboardUIState['watchlistSortKey']) => void;
}
```

`setWatchlistSort` toggles order when the same key is selected, resets to `desc` for a new key.

### Error / Stale Data Coexistence

TanStack Query exposes `data` and `isError` as independent values. The dashboard
distinguishes three states per card:

| State | UI |
|-------|----|
| `!data && isLoading` | Full skeleton |
| `!data && isError` | Inline error message (e.g. "Failed to load…") |
| `data && isError` | Render the cached data + a small `StaleBadge` so the user knows the last refresh failed |
| `data && !isError` | Render the data normally |

This pattern keeps the user from staring at a skeleton while TanStack Query
retries in the background. AccountSummary, Watchlist, and MarketIndex all
implement it. AccountStatus shows "Loading…" on the initial fetch only — its
state is low-frequency enough that a subtle badge adds no value.

### Retry Policy (TanStack Query)

`src/lib/query-client.ts` overrides the defaults so failures surface quickly:

```typescript
{
  retry: 1,
  retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 3000),
  staleTime: 15_000,
  refetchOnWindowFocus: false,
}
```

Rationale: the library default of 3 retries with exponential backoff can hold
`isError` false for 10–30 seconds after a failure. Users perceive that as an
infinite loading spinner. Retrying once (~1–2 s) lets the dashboard flip to the
error/stale state within ~3 seconds while still absorbing transient blips.

## 7. API Integration Points

Endpoints are organized by domain. The Dashboard UI composes data from multiple domain resources (`portfolio`, `watchlist`, `market`, `stocks`) plus the `auth` status endpoint.

| Endpoint | Method | Purpose | Refetch |
|----------|--------|---------|---------|
| `/api/v1/auth/status` | GET | Account connection status | 60s |
| `/api/v1/portfolio/summary` | GET | Total assets, daily P&L | 30s (market hours) |
| `/api/v1/watchlist` | GET | Watchlist stocks | 30s (market hours) |
| `/api/v1/watchlist` | POST | Add stock `{ symbol }` | Invalidates `['watchlist']` |
| `/api/v1/watchlist/{item_id}` | DELETE | Remove stock by id | Invalidates `['watchlist']` |
| `/api/v1/watchlist/reorder` | PATCH | Reorder `{ ids: number[] }` | Invalidates `['watchlist']` |
| `/api/v1/stocks/search` | GET | Search stocks for add modal | On input (debounced 300ms) |
| `/api/v1/market/indices` | GET | KOSPI/KOSDAQ index data | 30s (market hours) |

### Polling Strategy

All polling queries use a conditional `refetchInterval`:

```typescript
refetchInterval: (query) => (isMarketHours() ? 30_000 : false),
```

Market hours helper (`lib/market-hours.ts`) returns `true` between 09:00 and 15:30 KST on weekdays. Outside of market hours, polling is disabled and data remains static.

### Backend Adapter

All endpoint responses are adapted from snake_case to camelCase in `lib/api/adapters.ts` before reaching components.

## 8. Responsive Design

### Breakpoints

| Name | Width | Tailwind Prefix |
|------|-------|-----------------|
| Mobile | < 768px | default |
| Tablet | 768–1023px | `md:` |
| Desktop | ≥ 1024px | `lg:` |

### Layout by Breakpoint

| Section | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Account Summary | Full width | 1/2 width | 1/2 width |
| Market Index | Full width | 1/2 width | 1/2 width |
| Watchlist | Full width, compact rows | Full width | Full width |
| Add modal | Full screen drawer | Centered modal | Centered modal |

### Mobile-Specific Behaviors

- Watchlist: The "X" remove button is always visible (the desktop hover-to-reveal pattern collapses to always-on on touch devices).
- Account Summary: Compact layout (P&L on single line).
