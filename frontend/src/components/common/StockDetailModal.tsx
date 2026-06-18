'use client';

import { useEffect, useState, type ReactNode } from 'react';

import dynamic from 'next/dynamic';

import { useQuery } from '@tanstack/react-query';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PeriodToggle from '@/components/common/PeriodToggle';
import PriceDisplay from '@/components/common/PriceDisplay';
import { fetchStockHistory } from '@/lib/api/charts';
import { useStockDetail } from '@/stores/stock-detail';
import type { ChartPeriod } from '@/types/charts';

// lightweight-charts touches `window`/`document` on import, so the chart is
// loaded client-side only.
const PriceChart = dynamic(() => import('@/components/common/PriceChart'), { ssr: false });

export default function StockDetailModal() {
  const activeSymbol = useStockDetail((state) => state.activeSymbol);
  const activeName = useStockDetail((state) => state.activeName);
  const close = useStockDetail((state) => state.close);
  const [period, setPeriod] = useState<ChartPeriod>('1m');

  const isOpen = activeSymbol !== null;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['stocks', activeSymbol, 'history', period],
    queryFn: () => fetchStockHistory(activeSymbol as string, period),
    enabled: isOpen,
  });

  // Dismiss on Escape so keyboard users can always close the modal.
  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, close]);

  if (!isOpen) return null;

  // Derive the header price line from the candle series: the last close is the
  // most recent price, and its delta vs the prior close drives the change.
  const candles = data?.candles ?? [];
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const price = last?.close ?? 0;
  const change = last && prev ? last.close - prev.close : 0;
  const changeRate = last && prev && prev.close !== 0 ? (change / prev.close) * 100 : 0;

  let chartArea: ReactNode;
  if (isLoading) {
    chartArea = <div className="h-80 animate-pulse rounded bg-gray-100" />;
  } else if (isError) {
    chartArea = (
      <p className="flex h-80 items-center justify-center text-sm text-gray-400">
        차트 데이터를 불러올 수 없습니다.
      </p>
    );
  } else if (candles.length === 0) {
    chartArea = (
      <p className="flex h-80 items-center justify-center text-sm text-gray-400">
        표시할 가격 데이터가 없습니다.
      </p>
    );
  } else {
    chartArea = <PriceChart candles={candles} />;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 md:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={`${activeName ?? activeSymbol} price chart`}
    >
      {/*
        The backdrop is a button hidden from the accessibility tree
        (aria-hidden + tabIndex -1). Keyboard users dismiss via Escape or the
        visible "Close" button, matching the AddStockModal pattern.
      */}
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default"
        onClick={close}
        tabIndex={-1}
        aria-hidden="true"
      />

      <div className="relative z-10 w-full max-w-2xl rounded-t-2xl bg-white p-5 shadow-xl md:rounded-2xl">
        <header className="mb-4 flex items-start justify-between">
          <div>
            <div className="flex items-baseline gap-2">
              <h2 className="text-lg font-semibold text-gray-900">{activeName ?? activeSymbol}</h2>
              <span className="font-mono text-xs text-gray-400">{activeSymbol}</span>
            </div>
            <div className="mt-1 flex items-baseline gap-2">
              <PriceDisplay
                value={price}
                className="text-xl font-semibold tabular-nums text-gray-900"
              />
              <ChangeDisplay amount={change} rate={changeRate} className="text-sm" />
            </div>
          </div>
          <button
            type="button"
            onClick={close}
            className="rounded p-1 text-sm text-gray-500 hover:bg-gray-100"
            aria-label="Close"
          >
            Close
          </button>
        </header>

        <div className="mb-3 flex justify-end">
          <PeriodToggle value={period} onChange={setPeriod} />
        </div>

        {chartArea}
      </div>
    </div>
  );
}
