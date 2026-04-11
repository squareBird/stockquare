// Stocks API calls. Currently exposes the symbol/name search endpoint
// used by the watchlist "add stock" modal.

import type { StockSearchResult } from '@/types/dashboard';

import { toStockSearchResult } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

// GET /api/v1/stocks/search returns an envelope `{items, count}` per backend
// STOCKS spec. We unwrap `items` before running the adapter.
interface StockSearchEnvelope {
  items: Parameters<typeof toStockSearchResult>[0][];
  count: number;
}

export async function searchStocks(query: string): Promise<StockSearchResult[]> {
  if (isMockEnabled()) return mockApi.searchStocks(query);
  const raw = await apiRequest<StockSearchEnvelope>('/api/v1/stocks/search', {
    query: { q: query },
  });
  return raw.items.map(toStockSearchResult);
}
