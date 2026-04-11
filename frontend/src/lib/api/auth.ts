// Auth API calls. Covers KIS account connection status.
// Body shapes are mapped from snake_case to camelCase via the adapter layer.

import type { AccountStatus } from '@/types/dashboard';

import { toAccountStatus } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

export async function fetchAccountStatus(): Promise<AccountStatus> {
  if (isMockEnabled()) return mockApi.getAccountStatus();
  const raw = await apiRequest<Parameters<typeof toAccountStatus>[0]>('/api/v1/auth/status');
  return toAccountStatus(raw);
}
