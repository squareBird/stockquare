// Market API calls. Covers index data (KOSPI, KOSDAQ) for the dashboard.

import type { MarketIndicesResult } from '@/types/dashboard';

import { toMarketIndex, toMarketIndexError } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

// GET /api/v1/market/indices returns an envelope `{indices, errors}` per
// backend MARKET spec. Partial failures surface as entries in `errors[]`
// while healthy indices still return HTTP 200. We pass both through to the
// UI so degraded cards can render beside healthy ones.
interface MarketIndicesEnvelope {
  indices: Parameters<typeof toMarketIndex>[0][];
  errors: Parameters<typeof toMarketIndexError>[0][];
}

export async function fetchMarketIndices(): Promise<MarketIndicesResult> {
  if (isMockEnabled()) return mockApi.getMarketIndices();
  const raw = await apiRequest<MarketIndicesEnvelope>('/api/v1/market/indices');
  return {
    indices: raw.indices.map(toMarketIndex),
    errors: raw.errors.map(toMarketIndexError),
  };
}
