'use client';

import { useState } from 'react';

import type { Country } from '@/types/dashboard';

import KRMarketIndexPanel from './KRMarketIndexPanel';
import MarketIndexTabs from './MarketIndexTabs';
import PendingMarketIndexPanel from './PendingMarketIndexPanel';

// MarketIndex shell. Owns the active-country tab state and swaps the
// panel body based on the current selection. Each panel is a discrete
// component so switching tabs unmounts the previous one and naturally
// stops its TanStack Query polling — no explicit disable logic needed.
export default function MarketIndex() {
  const [country, setCountry] = useState<Country>('KR');
  const panelId = `market-panel-${country.toLowerCase()}`;
  const tabId = `market-tab-${country.toLowerCase()}`;

  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-card">
      <header className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
          Market Index
        </h2>
      </header>
      <MarketIndexTabs active={country} onChange={setCountry} />
      <div
        id={panelId}
        role="tabpanel"
        aria-labelledby={tabId}
        className="mt-4"
      >
        {country === 'KR' ? (
          <KRMarketIndexPanel />
        ) : (
          <PendingMarketIndexPanel country={country} />
        )}
      </div>
    </article>
  );
}
