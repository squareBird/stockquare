'use client';

import { useQuery } from '@tanstack/react-query';

import StaleBadge from '@/components/common/StaleBadge';
import { useMarketPollingInterval } from '@/hooks/useMarketPolling';
import { fetchMarketIndices } from '@/lib/api/market';

import DegradedIndexCard from './DegradedIndexCard';
import IndexCard from './IndexCard';

// KR market indices panel. Fetches KOSPI/KOSDAQ from /market/indices.
// - Lazy fetch: this component only mounts when the KR tab is active, so
//   TanStack Query stops polling on tab switch automatically.
// - 60s cadence: MarketIndex uses a slower refetch than AccountSummary/Watchlist
//   because index values are less latency-sensitive than portfolio numbers.
// - SWR: staleTime matches refetchInterval so quickly flipping away and back
//   to KR does not retrigger an immediate refetch.
export default function KRMarketIndexPanel() {
  const refetchInterval = useMarketPollingInterval(60_000);
  const { data, isLoading, isError } = useQuery({
    queryKey: ['market', 'indices', 'KR'],
    queryFn: fetchMarketIndices,
    refetchInterval,
    staleTime: 60_000,
  });

  // Coexistence: if we have a cached payload AND the latest refetch failed,
  // keep showing the previous data with a small "stale" badge instead of
  // replacing everything with an error message.
  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <div className="flex flex-col gap-2">
      {showStaleBadge ? (
        <div className="flex justify-end">
          <StaleBadge />
        </div>
      ) : null}

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
    </div>
  );
}
