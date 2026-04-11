'use client';

import type { WatchlistItemError } from '@/types/dashboard';

interface DegradedWatchlistItemProps {
  error: WatchlistItemError;
  onRemove: (id: number) => void;
}

// `role="status"` + polite live region so screen readers don't get spammed
// on every poll tick when the error persists across refetches.
export default function DegradedWatchlistItem({ error, onRemove }: DegradedWatchlistItemProps) {
  return (
    <li
      className="group flex items-center justify-between gap-4 border-b border-gray-100 bg-amber-50/60 px-5 py-3 transition-colors last:border-b-0 hover:bg-amber-50"
      role="status"
      aria-live="polite"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="truncate font-medium text-gray-900">{error.symbol}</span>
          <span
            className="truncate font-mono text-xs text-amber-500"
            title={error.message}
          >
            {error.errorCode}
          </span>
        </div>
        <div className="mt-0.5 truncate text-xs text-amber-700" title={error.message}>
          {error.message}
        </div>
      </div>

      <div className="flex flex-col items-end gap-0.5 text-right">
        <span className="text-sm font-medium tabular-nums text-gray-400">—</span>
        <span className="text-xs text-gray-400">Lookup failed</span>
      </div>

      <button
        type="button"
        onClick={() => onRemove(error.id)}
        className="rounded p-1 text-gray-300 transition-opacity hover:bg-gray-100 hover:text-gray-600 md:opacity-0 md:group-hover:opacity-100"
        aria-label={`Remove ${error.symbol} from watchlist`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
        </svg>
      </button>
    </li>
  );
}
