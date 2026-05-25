'use client';

import StaleBadge from '@/components/common/StaleBadge';

import { usePortfolioHoldings } from '../_hooks/usePortfolioHoldings';

import AllocationChart from './AllocationChart';

export default function AllocationSection() {
  const { data, isLoading, isError } = usePortfolioHoldings();

  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-card">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
          Asset Allocation
        </h2>
        {showStaleBadge ? <StaleBadge /> : null}
      </header>

      {isLoading ? (
        <div className="space-y-3">
          <div className="h-3 w-full animate-pulse rounded-full bg-gray-100" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-gray-100" />
          <div className="h-4 w-1/3 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="text-sm text-gain-strong">Failed to load holdings.</p>
      ) : null}

      {data ? <AllocationChart holdings={data.holdings} /> : null}
    </article>
  );
}
