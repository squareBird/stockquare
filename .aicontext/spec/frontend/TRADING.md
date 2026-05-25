# Trading Spec

Order-entry page with a two-step confirmation flow and a mode banner that
makes the REAL vs MOCK context unmissable. This page handles the only
mutations in the app that affect real money, so safety UX dominates the
design.

Route: `/trading`

## Layout

```
┌─────────────────────────────────────────────────┐
│  Global Header (nav tabs + account status)     │
├─────────────────────────────────────────────────┤
│  ModeBanner (full-width, REAL dark / MOCK gray)│
├─────────────────────────────────────────────────┤
│  Toast region (order result, auto-dismiss)      │
├───────────────────────┬─────────────────────────┤
│  Symbol card          │  Order Entry card       │
│   SymbolPicker        │   Side tabs (buy/sell)  │
│   QuotePanel          │   Type (limit/market)   │
│                       │   Qty / Price           │
│                       │   Estimated amount      │
│                       │   [Place Order]         │
├───────────────────────┴─────────────────────────┤
│  Order History (sortable table + cancel)       │
└─────────────────────────────────────────────────┘
```

On `lg:` and above the two upper cards sit in a 2-column grid
(`lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]`). Below `lg:` they stack.

## 1. ModeBanner

Full-width strip rendered **outside** the main container so it spans the
viewport. Reads `auth/status.account_mode` via TanStack Query.

- `real` → dark charcoal (`bg-surface-inverse`) strip with white text and
  a single red `●` dot indicating "live". Red is allowed here as a data
  signal (market is live) rather than a UI affordance.
- `mock` → neutral gray strip with dashed bottom border and "Mock
  Simulator" label.
- Unknown mode → nothing rendered.

Red is explicitly avoided as the banner background to preserve the
red-gain convention (the banner is UI, not data).

## 2. SymbolPicker

Reuses the `/api/v1/stocks/search` endpoint from the Dashboard add-stock
flow. Debounced 300 ms; `enabled` when trimmed query length ≥ 1.

Props:
```typescript
interface SymbolPickerProps {
  selected: StockSearchResult | null;
  onSelect: (stock: StockSearchResult) => void;
}
```

Query key: `['stocks', 'search', debouncedQuery]`. The Dashboard add-stock
modal uses the same key — caches are shared across pages.

## 3. QuotePanel

Placeholder component for Phase 2. Renders the selected symbol's name +
market plus a `₩0` skeleton. The live quote endpoint lands in Phase 2.5
per backend `STOCKS.md`; the placeholder preserves layout so the swap
doesn't require a reflow.

## 4. OrderEntry

Pure form component. All state local (useState). Does **not** submit
directly — it raises `onSubmit(request)` to the parent workspace, which
then opens the `OrderConfirmDialog`.

### Fields

| Field | Control | Notes |
|-------|---------|-------|
| Side | radio-group pill (buy/sell) | Korean convention: buy = red, sell = blue |
| Type | radio-group small pill (limit/market) | Market disables the price input |
| Quantity | `<input type="number">` | min 0, right-aligned tabular-nums |
| Price | `<input type="number">` | Disabled when type === `market` |
| Estimated amount | computed `quantity * price` | Shown in a gray summary box |
| Submit button | `type="submit"` | Disabled until symbol + qty + (market or price) |

### Styling

Active buy/sell buttons use `gain` / `loss` tokens to reinforce the
Korean red/blue convention. The submit CTA inherits the same red/blue
depending on the selected side.

## 5. OrderConfirmDialog

Two-step modal that opens when the parent workspace receives an
`OrderRequest`. Step 1 shows the review (symbol, side+type, qty, price,
estimated amount, mode badge). Step 2 replaces the primary action label
with "주문 제출" and adds a caution line. Escape closes the dialog;
backdrop click closes. Follows the same a11y pattern as AddStockModal
(backdrop is a `<button tabIndex={-1} aria-hidden="true">`).

Mode badge inside the dialog:
- `real` → dark charcoal pill with red dot
- `mock` → neutral dashed pill

The "submit" button label is computed via a `let submitLabel` + if/else
ladder (no nested ternary — lint rule).

## 6. OrderHistory

Card-wrapped table. Reuses the cached-data / stale-badge / full-error
coexistence pattern from Dashboard cards. `refetchInterval: 15_000`
(shorter than market-hours polling because order state can change between
ticks).

Columns: Symbol (name + monospace code), Side + Type abbr, Qty, Price,
Status pill, Action (`Cancel` button when status is `pending` or
`accepted`, otherwise `—`).

Mutation: `cancelOrder(id)` → invalidates `['orders']`.

Status pill colors:
- `pending`: gray-100
- `accepted` / `partially_filled`: brand-50
- `filled`: emerald-50
- `cancelled`: gray-100
- `rejected`: amber-50 (destructive, not red — red reserved for gain)

## 7. TradingWorkspace glue component

Holds the shared state between SymbolPicker, QuotePanel, OrderEntry,
OrderConfirmDialog, OrderHistory: `selectedSymbol`, `pendingRequest`,
`toast`. Also owns the `placeOrder` mutation with success/error toasts.

Client Component (single 'use client' entrypoint) so the page file stays
a Server Component and can simply compose `<ModeBanner />` + `<main>` +
`<TradingWorkspace />`.

## 8. Types

```typescript
type OrderSide = 'buy' | 'sell';
type OrderType = 'limit' | 'market';
type OrderStatus =
  | 'pending'
  | 'accepted'
  | 'partially_filled'
  | 'filled'
  | 'cancelled'
  | 'rejected';

interface Order {
  id: number;
  symbol: string;
  name: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  price: number;           // 0 for market orders
  filledQuantity: number;
  filledPrice: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
}

interface OrderRequest {
  symbol: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  price: number;
}

interface OrderModifyRequest {
  quantity?: number;
  price?: number;
}

interface OrdersResult {
  orders: Order[];
  count: number;
}
```

All live in `src/types/orders.ts`.

## 9. API integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/status` | GET | Drives ModeBanner and confirm-dialog badge |
| `/api/v1/stocks/search` | GET | SymbolPicker (shared with Dashboard) |
| `/api/v1/orders` | GET | OrderHistory list |
| `/api/v1/orders` | POST | OrderEntry submit (goes through confirm dialog) |
| `/api/v1/orders/{id}` | GET | Single-order detail (future) |
| `/api/v1/orders/{id}` | PATCH | Order modify (future — currently no UI) |
| `/api/v1/orders/{id}` | DELETE | Cancel button in OrderHistory |

All mutation endpoints (POST/PATCH/DELETE) receive the
`Content-Type: application/json` header per the shared `apiRequest`
helper.

## 10. State Management

| Data | Type | Tool | Key / Scope |
|------|------|------|-------------|
| Account status (drives mode banner) | Server | TanStack Query | `['auth', 'status']` |
| Stock search | Server | TanStack Query | `['stocks', 'search', q]` |
| Orders list | Server | TanStack Query | `['orders']` |
| Selected symbol | Local | `useState` | `TradingWorkspace` |
| Pending confirmation | Local | `useState` | `TradingWorkspace` |
| Toast | Local | `useState` | `TradingWorkspace` |
| Order form fields | Local | `useState` | `OrderEntry` |

## 11. Safety UX requirements (captain checklist)

- ☑ Confirmation dialog — `OrderConfirmDialog` (Section 5)
- ☑ Double-check — two-step flow (review → final confirm)
- ☑ Success/error toast — `TradingWorkspace` renders a dismissible
  status region after the mutation resolves
- ☑ REAL mode badge — `ModeBanner` full-width strip + reinforced in the
  confirm dialog header
- ☑ Order amount display — `OrderEntry` estimated-amount box and
  `OrderConfirmDialog` summary dl
