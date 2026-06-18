// Chart domain types. The backend GET /api/v1/stocks/{symbol}/history endpoint
// returns an OHLCV candle series; these types are what the chart components
// consume after passing through the adapter layer in `lib/api/adapters.ts`.
//
// Phase 1 ships daily candles only (1w/1m/3m/1y). Intraday `1d` minute candles
// are deferred to Phase 2 per the backend STOCKS spec.

export type ChartPeriod = '1w' | '1m' | '3m' | '1y';

// lightweight-charts consumes daily `time` as an ISO 'yyyy-mm-dd' string.
export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockHistoryResult {
  symbol: string;
  period: ChartPeriod;
  candles: Candle[];
}
