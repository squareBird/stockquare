// Portfolio domain types. Backend responses are snake_case;
// these camelCase types are what components consume after passing through
// the adapter layer in `lib/api/adapters.ts`.

export interface Holding {
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

// Degraded entry for a holding whose KIS price lookup failed.
// The backend still returns the row with its symbol so the UI can render
// the position with missing live data.
export interface HoldingError {
  symbol: string;
  name: string;
  quantity: number;
  avgPurchasePrice: number;
  purchaseAmount: number;
  errorCode: string;
  message: string;
}

export interface HoldingsResult {
  holdings: Holding[];
  errors: HoldingError[];
}
