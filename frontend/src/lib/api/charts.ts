// Chart history API. GET /api/v1/stocks/{symbol}/history returns an OHLCV
// candle series (envelope `{symbol, period, candles}`) backing the price chart.

import type { ChartInterval, StockHistoryResult } from '@/types/charts';

import { toStockHistory } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

interface CandleResponse {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface StockHistoryEnvelope {
  symbol: string;
  interval: ChartInterval;
  candles: CandleResponse[];
}

export async function fetchStockHistory(
  symbol: string,
  interval: ChartInterval,
): Promise<StockHistoryResult> {
  if (isMockEnabled()) return mockApi.getStockHistory(symbol, interval);
  const raw = await apiRequest<StockHistoryEnvelope>(`/api/v1/stocks/${symbol}/history`, {
    query: { interval },
  });
  return toStockHistory(raw);
}
