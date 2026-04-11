'use client';

import { useQuery } from '@tanstack/react-query';

import StaleBadge from '@/components/common/StaleBadge';
import { fetchMarketIndices } from '@/lib/api/market';

import { useMarketPollingInterval } from '../_hooks/useMarketPolling';

import DegradedIndexCard from './DegradedIndexCard';
import IndexCard from './IndexCard';

export default function MarketIndex() {
  const refetchInterval = useMarketPollingInterval();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['market', 'indices'],
    queryFn: fetchMarketIndices,
    refetchInterval,
  });

  // Coexistence: if we have a cached payload AND the latest refetch failed,
  // keep showing the previous data with a small "stale" badge instead of
  // replacing everything with an error message.
  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
          Market Index
        </h2>
        {showStaleBadge ? <StaleBadge /> : null}
      </header>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div className="h-24 animate-pulse rounded-lg bg-gray-100" />
          <div className="h-24 animate-pulse rounded-lg bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="text-sm text-red-500">Failed to load market indices.</p>
      ) : null}

      {data ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {data.indices.map((index) => (
            <IndexCard key={index.code} index={index} />
          ))}
          {data.errors.map((error) => (
            <DegradedIndexCard key={error.code} error={error} />
          ))}
        </div>
      ) : null}
    </article>
  );
}
