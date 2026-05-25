'use client';

import { useState } from 'react';

import StaleBadge from '@/components/common/StaleBadge';

import { usePortfolioHoldings } from '../_hooks/usePortfolioHoldings';

import HoldingsTable from './HoldingsTable';

type SortKey = 'name' | 'profitRate' | 'evaluationAmount';

export default function HoldingsSection() {
  const { data, isLoading, isError } = usePortfolioHoldings();
  const [sortKey, setSortKey] = useState<SortKey>('evaluationAmount');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const handleSortChange = (key: SortKey) => {
    if (key === sortKey) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortOrder('desc');
  };

  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;
  const totalCount = (data?.holdings.length ?? 0) + (data?.errors.length ?? 0);

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-card">
      <header className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">Holdings</h2>
          {showStaleBadge ? <StaleBadge /> : null}
        </div>
      </header>

      {isLoading ? (
        <div className="space-y-2 p-5">
          <div className="h-12 animate-pulse rounded bg-gray-100" />
          <div className="h-12 animate-pulse rounded bg-gray-100" />
          <div className="h-12 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="p-5 text-sm text-gain-strong">Failed to load holdings.</p>
      ) : null}

      {!showFullError && data && totalCount === 0 ? (
        <p className="p-8 text-center text-sm text-gray-400">
          보유 종목이 없습니다. Trading 페이지에서 첫 주문을 제출해 보세요.
        </p>
      ) : null}

      {data && totalCount > 0 ? (
        <div className="overflow-x-auto">
          <HoldingsTable
            data={data}
            sortKey={sortKey}
            sortOrder={sortOrder}
            onSortChange={handleSortChange}
          />
        </div>
      ) : null}
    </article>
  );
}
