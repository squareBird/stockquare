'use client';

import { formatKrw, formatVolume } from '@/lib/format';
import type { HoldingError } from '@/types/portfolio';

interface DegradedHoldingRowProps {
  error: HoldingError;
}

// `aria-live="polite"` without a role override (jsx-a11y rejects explicit
// `role="status"` on `<tr>` because rows already have an implicit `row` role).
// The polite live region still announces the row without spamming screen
// readers on every polling cycle.
export default function DegradedHoldingRow({ error }: DegradedHoldingRowProps) {
  return (
    <tr
      className="border-b border-gray-100 bg-amber-50/60 last:border-b-0"
      aria-live="polite"
    >
      <td className="px-4 py-3">
        <div className="flex flex-col">
          <span className="font-medium text-gray-900">{error.name}</span>
          <span className="font-mono text-xs text-amber-600" title={error.message}>
            {error.errorCode}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
        {formatVolume(error.quantity)}
      </td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-700">
        {formatKrw(error.avgPurchasePrice)}
      </td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-400">—</td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-400">—</td>
      <td className="px-4 py-3 text-right text-xs text-amber-700" title={error.message}>
        Lookup failed
      </td>
    </tr>
  );
}
