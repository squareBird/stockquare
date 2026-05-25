'use client';

import { useEffect, useState } from 'react';

import { isMarketHours } from '@/lib/market-hours';

// Returns a TanStack Query `refetchInterval` value that polls on the given
// cadence during Korean market hours and disables polling outside those
// windows. Re-evaluates once per minute so hooks flip on/off when the market
// opens/closes without the user reloading the page.
//
// Shared across Dashboard, Portfolio, and Trading pages. Lives in `src/hooks/`
// per PROJECT_STRUCTURE.md (shared custom hooks root).
//
// `intervalMs` defaults to 30s (used by AccountSummary / Watchlist / Portfolio
// holdings). MarketIndex overrides to 60s because the country-tab UI only
// polls the active tab and a slower cadence is sufficient for index values.
export function useMarketPollingInterval(intervalMs: number = 30_000): number | false {
  const [marketOpen, setMarketOpen] = useState(() => isMarketHours());

  useEffect(() => {
    const tick = () => setMarketOpen(isMarketHours());
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  return marketOpen ? intervalMs : false;
}
