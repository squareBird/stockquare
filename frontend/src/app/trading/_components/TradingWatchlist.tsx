'use client';

import { useQuery } from '@tanstack/react-query';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PriceDisplay from '@/components/common/PriceDisplay';
import StaleBadge from '@/components/common/StaleBadge';
import { useMarketPollingInterval } from '@/hooks/useMarketPolling';
import { fetchWatchlist } from '@/lib/api/watchlist';
import type { StockSearchResult } from '@/types/dashboard';

interface TradingWatchlistProps {
  selectedSymbol: string | null;
  onSelect: (stock: StockSearchResult) => void;
}

// Left-rail watchlist for the Trading page. Clicking a row selects that symbol
// for the inline chart + order entry (no modal). Watchlist items carry no
// market field, so KR is assumed — the list is KR-only in Phase 1.
export default function TradingWatchlist({ selectedSymbol, onSelect }: TradingWatchlistProps) {
  const refetchInterval = useMarketPollingInterval();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
    refetchInterval,
  });

  const items = data?.items ?? [];
  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-card">
      <header className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
          관심종목
        </h2>
        {showStaleBadge ? <StaleBadge /> : null}
      </header>

      {isLoading ? (
        <div className="space-y-2 p-4">
          <div className="h-10 animate-pulse rounded bg-gray-100" />
          <div className="h-10 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="p-4 text-sm text-red-500">관심종목을 불러올 수 없습니다.</p>
      ) : null}

      {!showFullError && data && items.length === 0 ? (
        <p className="p-6 text-center text-sm text-gray-400">
          관심종목이 없습니다. 대시보드에서 추가하세요.
        </p>
      ) : null}

      {items.length > 0 ? (
        <ul>
          {items.map((item) => {
            const isActive = item.symbol === selectedSymbol;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onSelect({ symbol: item.symbol, name: item.name, market: 'KOSPI' })}
                  className={`flex w-full items-center justify-between gap-3 border-b border-gray-100 px-4 py-2.5 text-left transition-colors last:border-b-0 ${
                    isActive ? 'bg-brand-50' : 'hover:bg-gray-50'
                  }`}
                  aria-pressed={isActive}
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-gray-900">{item.name}</div>
                    <div className="font-mono text-xs text-gray-400">{item.symbol}</div>
                  </div>
                  <div className="flex flex-col items-end gap-0.5">
                    <PriceDisplay
                      value={item.price}
                      className="text-sm font-medium tabular-nums text-gray-900"
                    />
                    <ChangeDisplay amount={item.change} rate={item.changeRate} className="text-xs" />
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </article>
  );
}
