'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchAccountStatus } from '@/lib/api/auth';

// Full-width banner shown directly under the global header on the Trading
// page. The designer's spec calls for a dark charcoal "REAL" strip (NOT red
// — red is reserved for gain) and a neutral "MOCK" pill for the simulator
// case. The component renders inside the page (not the global header) so
// it only appears when the user is actually on the Trading page.
export default function ModeBanner() {
  const { data } = useQuery({
    queryKey: ['auth', 'status'],
    queryFn: fetchAccountStatus,
    refetchInterval: 60_000,
  });

  const mode = data?.accountMode;

  if (mode === 'real') {
    return (
      <div
        className="w-full bg-surface-inverse px-4 py-2 text-center text-xs font-bold uppercase tracking-widest text-white"
        role="status"
        aria-label="Real trading mode — orders place real money at risk"
      >
        <span className="mr-2 inline-block h-2 w-2 rounded-full bg-gain align-middle" aria-hidden="true" />
        Real Trading Mode · 주문 제출 시 실제 주문이 체결됩니다
      </div>
    );
  }

  if (mode === 'mock') {
    return (
      <div
        className="w-full border-b border-dashed border-gray-200 bg-gray-50 px-4 py-1.5 text-center text-[11px] font-semibold uppercase tracking-wider text-gray-500"
        role="status"
      >
        Mock Simulator · 실제 주문이 체결되지 않습니다
      </div>
    );
  }

  return null;
}
