// Portfolio API calls. Covers the account summary used by Dashboard
// and the holdings list used by the Portfolio page.

import type { AccountSummary } from '@/types/dashboard';
import type { HoldingsResult } from '@/types/portfolio';

import { toAccountSummary, toHolding, toHoldingError } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

export async function fetchAccountSummary(): Promise<AccountSummary> {
  if (isMockEnabled()) return mockApi.getAccountSummary();
  const raw = await apiRequest<Parameters<typeof toAccountSummary>[0]>(
    '/api/v1/portfolio/summary',
  );
  return toAccountSummary(raw);
}

// GET /api/v1/portfolio/holdings returns an envelope
// `{holdings, errors, count}` per backend PORTFOLIO spec. KIS price lookup
// failures surface in `errors[]` with the stored position metadata
// (quantity, avg_purchase_price) still present.
interface HoldingsEnvelope {
  holdings: Parameters<typeof toHolding>[0][];
  errors: Parameters<typeof toHoldingError>[0][];
  count: number;
}

export async function fetchHoldings(): Promise<HoldingsResult> {
  if (isMockEnabled()) return mockApi.getHoldings();
  const raw = await apiRequest<HoldingsEnvelope>('/api/v1/portfolio/holdings');
  return {
    holdings: raw.holdings.map(toHolding),
    errors: raw.errors.map(toHoldingError),
  };
}
