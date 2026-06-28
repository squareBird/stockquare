// Chart domain types. The backend GET /api/v1/stocks/{symbol}/history endpoint
// returns an OHLCV candle series; these types are what the chart components
// consume after passing through the adapter layer in `lib/api/adapters.ts`.
//
// `interval` selects the candle granularity: 분봉(min) / 일봉(day, default) /
// 주봉(week) / 월봉(month). The visible range is derived per interval by the
// backend (see the STOCKS spec); the client only picks the granularity.

export type ChartInterval = 'min' | 'day' | 'week' | 'month';

// lightweight-charts consumes `time` as an ISO 'yyyy-mm-dd' string for
// day/week/month candles, or an epoch-second number for intraday minute candles.
export interface Candle {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StockHistoryResult {
  symbol: string;
  interval: ChartInterval;
  candles: Candle[];
}
