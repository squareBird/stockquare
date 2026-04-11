// Portfolio API calls. Covers the account-level summary (cash + holdings + daily P&L).

import type { AccountSummary } from '@/types/dashboard';

import { toAccountSummary } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

export async function fetchAccountSummary(): Promise<AccountSummary> {
  if (isMockEnabled()) return mockApi.getAccountSummary();
  const raw = await apiRequest<Parameters<typeof toAccountSummary>[0]>(
    '/api/v1/portfolio/summary',
  );
  return toAccountSummary(raw);
}
