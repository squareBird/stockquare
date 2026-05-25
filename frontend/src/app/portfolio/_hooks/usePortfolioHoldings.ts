'use client';

import { useQuery } from '@tanstack/react-query';

import { useMarketPollingInterval } from '@/hooks/useMarketPolling';
import { fetchHoldings } from '@/lib/api/portfolio';

export function usePortfolioHoldings() {
  const refetchInterval = useMarketPollingInterval();
  return useQuery({
    queryKey: ['portfolio', 'holdings'],
    queryFn: fetchHoldings,
    refetchInterval,
  });
}
