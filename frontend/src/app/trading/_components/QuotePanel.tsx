'use client';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PriceDisplay from '@/components/common/PriceDisplay';
import type { StockSearchResult } from '@/types/dashboard';

interface QuotePanelProps {
  symbol: StockSearchResult | null;
}

// Minimal placeholder quote panel for Phase 2. A live quote endpoint would
// plug in here via TanStack Query keyed by symbol; until the backend `/stocks/{symbol}`
// endpoint ships (Phase 2.5), we show the selected symbol metadata only.
export default function QuotePanel({ symbol }: QuotePanelProps) {
  if (!symbol) {
    return (
      <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-400">
        Select a symbol to view the live quote.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-base font-semibold text-gray-900">{symbol.name}</div>
          <div className="font-mono text-xs text-gray-400">
            {symbol.symbol} · {symbol.market}
          </div>
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-400">
          Quote
        </span>
      </div>

      {/*
        Placeholder price/change area. Replace with a live `useStockQuote(symbol)`
        hook when the backend single-stock endpoint lands. Preserving the layout
        means the swap won't require a re-flow.
      */}
      <div className="mt-4 flex items-baseline justify-between border-t border-gray-100 pt-3">
        <PriceDisplay value={0} className="text-2xl font-bold tabular-nums text-gray-400" />
        <ChangeDisplay amount={0} rate={0} className="text-sm" />
      </div>
      <p className="mt-2 text-[11px] text-gray-400">
        Live quote data coming in Phase 2.5 — see backend `STOCKS.md` roadmap.
      </p>
    </div>
  );
}
