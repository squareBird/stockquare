'use client';

import { useMemo, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import StaleBadge from '@/components/common/StaleBadge';
import { useMarketPollingInterval } from '@/hooks/useMarketPolling';
import { addWatchlistItem, fetchWatchlist, removeWatchlistItem } from '@/lib/api/watchlist';
import { useDashboardUI, type WatchlistSortKey } from '@/stores/dashboard-ui';
import type { WatchlistItem as WatchlistItemType } from '@/types/dashboard';

import AddStockModal from './AddStockModal';
import DegradedWatchlistItem from './DegradedWatchlistItem';
import WatchlistItem from './WatchlistItem';

const WATCHLIST_QUERY_KEY = ['watchlist'] as const;

const SORT_OPTIONS: Array<{ key: WatchlistSortKey; label: string }> = [
  { key: 'changeRate', label: 'Change' },
  { key: 'name', label: 'Name' },
  { key: 'price', label: 'Price' },
];

function sortWatchlist(
  items: WatchlistItemType[],
  key: WatchlistSortKey,
  order: 'asc' | 'desc',
): WatchlistItemType[] {
  const multiplier = order === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    if (key === 'name') {
      return a.name.localeCompare(b.name, 'ko') * multiplier;
    }
    if (key === 'price') {
      return (a.price - b.price) * multiplier;
    }
    return (a.changeRate - b.changeRate) * multiplier;
  });
}

export default function Watchlist() {
  const queryClient = useQueryClient();
  const refetchInterval = useMarketPollingInterval();
  const [isAddModalOpen, setAddModalOpen] = useState(false);

  const sortKey = useDashboardUI((state) => state.watchlistSortKey);
  const sortOrder = useDashboardUI((state) => state.watchlistSortOrder);
  const setSort = useDashboardUI((state) => state.setWatchlistSort);

  const { data, isLoading, isError } = useQuery({
    queryKey: WATCHLIST_QUERY_KEY,
    queryFn: fetchWatchlist,
    refetchInterval,
  });

  const addMutation = useMutation({
    mutationFn: addWatchlistItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WATCHLIST_QUERY_KEY });
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeWatchlistItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WATCHLIST_QUERY_KEY });
    },
  });

  const sortedItems = useMemo(
    () => (data ? sortWatchlist(data.items, sortKey, sortOrder) : []),
    [data, sortKey, sortOrder],
  );
  const errorItems = data?.errors ?? [];
  const totalCount = sortedItems.length + errorItems.length;

  // Coexistence: a cached payload + a failed refetch shows the stale badge;
  // only a fresh load failure replaces the list with an error message.
  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-card">
      <header className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <div className="flex items-center gap-4">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">Watchlist</h2>
          {showStaleBadge ? <StaleBadge /> : null}
          <div
            className="flex items-center gap-1 text-xs text-gray-500"
            role="group"
            aria-label="Sort watchlist"
          >
            {SORT_OPTIONS.map((option) => {
              const isActive = sortKey === option.key;
              return (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => setSort(option.key)}
                  className={`flex items-center gap-0.5 rounded px-2 py-1 font-medium transition-colors ${
                    isActive
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-500 hover:bg-gray-100'
                  }`}
                  aria-pressed={isActive}
                >
                  {option.label}
                  {isActive ? (
                    <span aria-hidden="true">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setAddModalOpen(true)}
          className="rounded-md bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200"
        >
          + Add
        </button>
      </header>

      {isLoading ? (
        <div className="space-y-2 p-5">
          <div className="h-12 animate-pulse rounded bg-gray-100" />
          <div className="h-12 animate-pulse rounded bg-gray-100" />
          <div className="h-12 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="p-5 text-sm text-red-500">Failed to load watchlist.</p>
      ) : null}

      {!showFullError && data && totalCount === 0 ? (
        <p className="p-8 text-center text-sm text-gray-400">
          No stocks yet. Click &ldquo;+ Add&rdquo; to start tracking.
        </p>
      ) : null}

      {totalCount > 0 ? (
        <>
          {sortedItems.length > 0 ? (
            <ul>
              {sortedItems.map((item) => (
                <WatchlistItem
                  key={item.id}
                  item={item}
                  onRemove={(id) => removeMutation.mutate(id)}
                />
              ))}
            </ul>
          ) : null}

          {errorItems.length > 0 ? (
            <>
              {/*
                Dedicated bucket for degraded rows so they don't compete with
                sort order. The heading signals they are pinned below and
                explains why they aren't responding to the sort buttons.
              */}
              <div className="flex items-center gap-2 border-t border-gray-100 bg-amber-50/40 px-5 py-2 text-[11px] font-semibold uppercase tracking-wider text-amber-700">
                Unavailable ({errorItems.length})
              </div>
              <ul>
                {errorItems.map((error) => (
                  <DegradedWatchlistItem
                    key={error.id}
                    error={error}
                    onRemove={(id) => removeMutation.mutate(id)}
                  />
                ))}
              </ul>
            </>
          ) : null}
        </>
      ) : null}

      <AddStockModal
        isOpen={isAddModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdd={(symbol) => addMutation.mutate(symbol)}
      />
    </article>
  );
}
