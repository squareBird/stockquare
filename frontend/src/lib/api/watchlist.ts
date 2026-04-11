// Watchlist API calls. Covers listing, adding, removing, and reordering items.
//
// Backend contract: `.aicontext/spec/backend/WATCHLIST.md`.
// Two known deferrals (tracked but intentionally NOT fixed here):
//   1. `addWatchlistItem` declares `Promise<WatchlistItem>` but the backend
//      POST response is narrower (no price/change/volume). The caller
//      discards the return value and refreshes via TanStack Query
//      invalidation, so the type lie has no runtime impact today.
//   2. `reorderWatchlist` sends `{ids: number[]}` but the spec body is
//      `{order: [{id, sort_order}]}`. No UI calls this function in Phase 1;
//      when drag-and-drop reorder lands in Phase 2, update the body shape.

import type { WatchlistItem, WatchlistResult } from '@/types/dashboard';

import { toWatchlistItem, toWatchlistItemError } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

// GET /api/v1/watchlist returns an envelope `{items, errors, count}` per
// backend WATCHLIST spec. Items whose KIS price lookup fails surface in
// `errors[]` so the UI can render degraded rows in place of price data.
interface WatchlistEnvelope {
  items: Parameters<typeof toWatchlistItem>[0][];
  errors: Parameters<typeof toWatchlistItemError>[0][];
  count: number;
}

export async function fetchWatchlist(): Promise<WatchlistResult> {
  if (isMockEnabled()) return mockApi.getWatchlist();
  const raw = await apiRequest<WatchlistEnvelope>('/api/v1/watchlist');
  return {
    items: raw.items.map(toWatchlistItem),
    errors: raw.errors.map(toWatchlistItemError),
  };
}

// NOTE: POST /api/v1/watchlist returns a NARROW object
// `{id, symbol, name, sort_order, created_at}` — it does not include
// price/change/volume fields. The caller (`addMutation` in Watchlist.tsx)
// discards this return value and refreshes the list via TanStack Query
// invalidation, so we keep the declared type loose and let the invalidated
// GET /watchlist call produce the authoritative enriched data.
export async function addWatchlistItem(symbol: string): Promise<WatchlistItem> {
  if (isMockEnabled()) return mockApi.addWatchlistItem(symbol);
  const raw = await apiRequest<Parameters<typeof toWatchlistItem>[0]>('/api/v1/watchlist', {
    method: 'POST',
    body: { symbol },
  });
  return toWatchlistItem(raw);
}

export async function removeWatchlistItem(id: number): Promise<void> {
  if (isMockEnabled()) {
    mockApi.removeWatchlistItem(id);
    return;
  }
  await apiRequest<null>(`/api/v1/watchlist/${id}`, { method: 'DELETE' });
}

export async function reorderWatchlist(ids: number[]): Promise<void> {
  if (isMockEnabled()) {
    mockApi.reorderWatchlist(ids);
    return;
  }
  await apiRequest<null>('/api/v1/watchlist/reorder', {
    method: 'PATCH',
    body: { ids },
  });
}
