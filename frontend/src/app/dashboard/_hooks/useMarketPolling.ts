'use client';

import { useEffect, useState } from 'react';

import { isMarketHours } from '@/lib/market-hours';

// Returns a TanStack Query `refetchInterval` value that polls every 30 seconds
// during Korean market hours and disables polling outside those windows.
// Re-evaluates once per minute so hooks flip on/off when the market opens/closes
// without the user reloading the page.
export function useMarketPollingInterval(): number | false {
  const [marketOpen, setMarketOpen] = useState(() => isMarketHours());

  useEffect(() => {
    const tick = () => setMarketOpen(isMarketHours());
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  return marketOpen ? 30_000 : false;
}
