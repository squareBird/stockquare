'use client';

import { useState, type ReactNode } from 'react';

import dynamic from 'next/dynamic';

import { useQuery } from '@tanstack/react-query';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PeriodToggle from '@/components/common/PeriodToggle';
import PriceDisplay from '@/components/common/PriceDisplay';
import { fetchStockHistory } from '@/lib/api/charts';
import type { ChartPeriod } from '@/types/charts';

// lightweight-charts touches `window`/`document` on import, so the chart is
// loaded client-side only.
const PriceChart = dynamic(() => import('@/components/common/PriceChart'), { ssr: false });

interface SymbolChartProps {
  symbol: string;
  name?: string | null;
  // Optional element rendered at the top-right of the header (e.g. the modal's
  // Close button). The inline trading panel leaves it empty.
  headerRight?: ReactNode;
}

// Self-contained candlestick view: header price line + period toggle + chart,
// shared by the global StockDetailModal and the Trading page's inline panel.
// Phase 1 charting is KR-only (domestic KIS daily candles, KRW); overseas
// symbols degrade to a "not yet supported" message instead of firing a failing
// history request.
export default function SymbolChart({ symbol, name, headerRight }: SymbolChartProps) {
  const [period, setPeriod] = useState<ChartPeriod>('1m');
  const isKrSymbol = /^\d{6}$/.test(symbol);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['stocks', symbol, 'history', period],
    queryFn: () => fetchStockHistory(symbol, period),
    enabled: isKrSymbol,
  });

  // Derive the header price line from the candle series: the last close is the
  // most recent price, and its delta vs the prior close drives the change.
  const candles = data?.candles ?? [];
  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const price = last?.close ?? 0;
  const change = last && prev ? last.close - prev.close : 0;
  const changeRate = last && prev && prev.close !== 0 ? (change / prev.close) * 100 : 0;

  let chartArea: ReactNode;
  if (!isKrSymbol) {
    chartArea = (
      <p className="flex h-80 items-center justify-center text-sm text-gray-400">
        해외 종목 차트는 아직 지원하지 않습니다.
      </p>
    );
  } else if (isLoading) {
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
    <div>
      <header className="mb-4 flex items-start justify-between">
        <div>
          <div className="flex items-baseline gap-2">
            <h2 className="text-lg font-semibold text-gray-900">{name ?? symbol}</h2>
            <span className="font-mono text-xs text-gray-400">{symbol}</span>
          </div>
          {isKrSymbol ? (
            <div className="mt-1 flex items-baseline gap-2">
              <PriceDisplay
                value={price}
                className="text-xl font-semibold tabular-nums text-gray-900"
              />
              <ChangeDisplay amount={change} rate={changeRate} className="text-sm" />
            </div>
          ) : (
            <div className="mt-1 text-xs text-gray-400">해외 종목 (Phase 2 예정)</div>
          )}
        </div>
        {headerRight}
      </header>

      <div className="mb-3 flex justify-end">
        <PeriodToggle value={period} onChange={setPeriod} />
      </div>

      {chartArea}
    </div>
  );
}
