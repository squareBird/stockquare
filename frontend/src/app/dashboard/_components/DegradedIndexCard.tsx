import WarningIcon from '@/components/common/WarningIcon';
import type { MarketIndexError } from '@/types/dashboard';

interface DegradedIndexCardProps {
  error: MarketIndexError;
}

// `role="status"` + polite live region (not `alert`) so the announcement
// does not pre-empt the user on every 30s poll when the error persists.
export default function DegradedIndexCard({ error }: DegradedIndexCardProps) {
  return (
    <div
      className="rounded-lg border border-amber-200 bg-amber-50 p-4"
      role="status"
      aria-live="polite"
      aria-label={`${error.name} lookup failed: ${error.message}`}
    >
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold text-gray-700">{error.name}</span>
        <span className="text-[10px] font-semibold uppercase text-amber-600">
          {error.errorCode}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-lg font-semibold text-amber-700">
        <WarningIcon size={16} />
        <span>Lookup failed</span>
      </div>
      <div className="mt-1 truncate text-xs text-amber-700 opacity-80" title={error.message}>
        {error.message}
      </div>
    </div>
  );
}
