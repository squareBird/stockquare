// Domain types used by the dashboard page.
// Backend responses are snake_case; these camelCase types are what components consume
// after passing through the adapter layer in `lib/api/adapters.ts`.

export type AccountConnectionStatus = 'connected' | 'disconnected' | 'error';

export type AccountMode = 'real' | 'mock';

export interface AccountStatus {
  status: AccountConnectionStatus;
  accountNumber?: string;
  accountMode?: AccountMode;
  message?: string;
}

export interface AccountSummary {
  totalAsset: number;
  dailyProfit: number;
  dailyProfitRate: number;
  cashBalance: number;
}

export interface WatchlistItem {
  id: number;
  sortOrder: number;
  symbol: string;
  name: string;
  price: number;
  change: number;
  changeRate: number;
  volume: number;
}

// Degraded entry for a watchlist row whose KIS price lookup failed.
// The backend still returns the row with its id/symbol so the UI can render
// a skeletonized card and let the user remove it.
export interface WatchlistItemError {
  id: number;
  symbol: string;
  errorCode: string;
  message: string;
}

export interface WatchlistResult {
  items: WatchlistItem[];
  errors: WatchlistItemError[];
}

export type MarketStatus = 'open' | 'closed' | 'pre_market';

// Country tab key for the MarketIndex dashboard card. KR is the only tab
// currently backed by a real query; US/JP/CN render a pending skeleton
// until the backend /market/indices endpoint gains a `country` filter.
export type Country = 'KR' | 'US' | 'JP' | 'CN';

export interface MarketIndex {
  code: string;
  name: string;
  value: number;
  change: number;
  changeRate: number;
  volume: number;
  status: MarketStatus;
}

// Degraded entry for a market index whose KIS lookup failed.
// The backend preserves `code`/`name` so the UI can render a labelled card
// in place of the missing value.
export interface MarketIndexError {
  code: string;
  name: string;
  errorCode: string;
  message: string;
}

export interface MarketIndicesResult {
  indices: MarketIndex[];
  errors: MarketIndexError[];
}

export interface StockSearchResult {
  symbol: string;
  name: string;
  market: string;
}
