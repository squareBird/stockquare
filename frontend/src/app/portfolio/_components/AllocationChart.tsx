'use client';

import { formatKrw } from '@/lib/format';
import type { Holding } from '@/types/portfolio';

interface AllocationChartProps {
  holdings: Holding[];
}

// Lightweight horizontal stacked-bar visualization of portfolio weights.
// Avoids pulling in a charting library for Phase 2; a richer donut chart
// can replace this component without touching the data flow.
const ALLOCATION_COLORS = [
  'bg-brand-600',
  'bg-brand-400',
  'bg-brand-200',
  'bg-gray-400',
  'bg-gray-300',
  'bg-gray-200',
] as const;

export default function AllocationChart({ holdings }: AllocationChartProps) {
  const totalValue = holdings.reduce((sum, h) => sum + h.evaluationAmount, 0);

  if (totalValue === 0 || holdings.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No positions to allocate.
      </div>
    );
  }

  const sorted = [...holdings].sort((a, b) => b.evaluationAmount - a.evaluationAmount);

  return (
    <div className="space-y-3">
      <div className="flex h-3 w-full overflow-hidden rounded-full border border-gray-200 bg-gray-100">
        {sorted.map((holding, index) => {
          const pct = (holding.evaluationAmount / totalValue) * 100;
          const color = ALLOCATION_COLORS[index % ALLOCATION_COLORS.length];
          return (
            <div
              key={holding.symbol}
              className={color}
              style={{ width: `${pct}%` }}
              aria-label={`${holding.name}: ${pct.toFixed(1)}%`}
              role="presentation"
            />
          );
        })}
      </div>

      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {sorted.map((holding, index) => {
          const pct = (holding.evaluationAmount / totalValue) * 100;
          const color = ALLOCATION_COLORS[index % ALLOCATION_COLORS.length];
          return (
            <li
              key={holding.symbol}
              className="flex items-center justify-between gap-2 text-xs"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />
                <span className="truncate font-medium text-gray-700">{holding.name}</span>
              </div>
              <div className="shrink-0 text-right tabular-nums text-gray-500">
                <span className="font-medium text-gray-900">{pct.toFixed(1)}%</span>
                <span className="ml-1 text-gray-400">· {formatKrw(holding.evaluationAmount)}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
