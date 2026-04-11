'use client';

import { useQuery } from '@tanstack/react-query';

import { fetchAccountStatus } from '@/lib/api/auth';

const LABEL_MAP = {
  connected: 'Connected',
  disconnected: 'Disconnected',
  error: 'Connection Error',
} as const;

const DOT_CLASS_MAP = {
  connected: 'bg-green-500 ring-2 ring-green-500/30 animate-pulse',
  disconnected: 'bg-gray-400',
  error: 'bg-red-500',
} as const;

const TEXT_CLASS_MAP = {
  connected: 'text-green-600',
  disconnected: 'text-gray-500',
  error: 'text-red-600',
} as const;

export default function AccountStatus() {
  const { data, isLoading } = useQuery({
    queryKey: ['auth', 'status'],
    queryFn: fetchAccountStatus,
    refetchInterval: 60_000,
  });

  if (isLoading || !data) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="h-2 w-2 animate-pulse rounded-full bg-gray-300" />
        <span>Loading…</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${DOT_CLASS_MAP[data.status]}`} />
      <span className={`font-medium ${TEXT_CLASS_MAP[data.status]}`}>
        {LABEL_MAP[data.status]}
      </span>
      {data.accountNumber ? (
        <span className="font-mono text-xs text-gray-500">{data.accountNumber}</span>
      ) : null}
      {data.message ? <span className="text-gray-400">· {data.message}</span> : null}
    </div>
  );
}
