'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchAccountStatus } from '@/lib/api/auth';

import ModeBadge from './ModeBadge';

const LABEL_MAP = {
  connected: 'Connected',
  disconnected: 'Disconnected',
  error: 'Error',
} as const;

const DOT_CLASS_MAP = {
  connected: 'bg-emerald-500 ring-2 ring-emerald-500/30 animate-pulse',
  disconnected: 'bg-gray-400',
  error: 'bg-gain',
} as const;

const TEXT_CLASS_MAP = {
  connected: 'text-emerald-600',
  disconnected: 'text-gray-500',
  error: 'text-gain-strong',
} as const;

// Compact version of AccountStatus that lives in the global header. Mobile
// collapses the text labels but keeps the status dot and mode badge visible.
export default function HeaderAccount() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['auth', 'status'],
    queryFn: fetchAccountStatus,
    refetchInterval: 60_000,
  });

  if (!data && isError) {
    return (
      <div
        className="flex items-center gap-2 text-xs text-gain-strong"
        role="status"
        aria-label="Account status unavailable"
      >
        <span className="h-2 w-2 rounded-full bg-gain" />
        <span className="hidden sm:inline font-medium">Connection error</span>
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="flex items-center gap-2 text-xs text-gray-400">
        <span className="h-2 w-2 animate-pulse rounded-full bg-gray-300" />
        <span className="hidden sm:inline">Loading…</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs sm:gap-3">
      <div className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${DOT_CLASS_MAP[data.status]}`} />
        <span
          className={`hidden font-medium sm:inline ${TEXT_CLASS_MAP[data.status]}`}
        >
          {LABEL_MAP[data.status]}
        </span>
        {data.accountNumber ? (
          <span className="hidden font-mono text-gray-500 sm:inline">
            {data.accountNumber}
          </span>
        ) : null}
      </div>
      <ModeBadge mode={data.accountMode} />
    </div>
  );
}
