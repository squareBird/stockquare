'use client';

import type { ReactNode } from 'react';

import { useQuery } from '@tanstack/react-query';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PriceDisplay from '@/components/common/PriceDisplay';
import StaleBadge from '@/components/common/StaleBadge';
import { fetchAccountSummary } from '@/lib/api/portfolio';

import { useMarketPollingInterval } from '../_hooks/useMarketPolling';

interface SummaryRowProps {
  label: string;
  children: ReactNode;
}

function SummaryRow({ label, children }: SummaryRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-gray-500">{label}</span>
      <span className="text-sm font-medium tabular-nums text-gray-800">{children}</span>
    </div>
  );
}

export default function AccountSummary() {
  const refetchInterval = useMarketPollingInterval();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['portfolio', 'summary'],
    queryFn: fetchAccountSummary,
    refetchInterval,
  });

  // Coexistence: if we have a cached snapshot AND the latest refetch failed,
  // keep rendering the previous numbers with a "stale" badge. Only suppress
  // the data entirely when we never successfully loaded in the first place.
  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <header className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wider text-gray-500">
          Account Summary
        </h2>
        {showStaleBadge ? <StaleBadge /> : null}
      </header>

      {isLoading ? (
        <div className="space-y-3">
          <div className="h-8 w-2/3 animate-pulse rounded bg-gray-100" />
          <div className="h-5 w-1/2 animate-pulse rounded bg-gray-100" />
          <div className="h-5 w-1/2 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="text-sm text-red-500">Failed to load account summary.</p>
      ) : null}

      {data ? (
        <div>
          <PriceDisplay
            value={data.totalAsset}
            className="block text-3xl font-bold tabular-nums tracking-tight text-gray-900"
          />

          <div className="mt-2">
            <ChangeDisplay
              amount={data.dailyProfit}
              rate={data.dailyProfitRate}
              className="text-base font-semibold"
            />
          </div>

          <div className="mt-4 space-y-0 border-t border-gray-100 pt-3">
            <SummaryRow label="Cash Balance">
              <PriceDisplay value={data.cashBalance} />
            </SummaryRow>
            <SummaryRow label="Holdings Value">
              <PriceDisplay value={data.totalAsset - data.cashBalance} />
            </SummaryRow>
          </div>
        </div>
      ) : null}
    </article>
  );
}
