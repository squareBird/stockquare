'use client';

import type { ChartPeriod } from '@/types/charts';

interface PeriodToggleProps {
  value: ChartPeriod;
  onChange: (period: ChartPeriod) => void;
}

const PERIODS: Array<{ key: ChartPeriod; label: string }> = [
  { key: '1w', label: '1W' },
  { key: '1m', label: '1M' },
  { key: '3m', label: '3M' },
  { key: '1y', label: '1Y' },
];

export default function PeriodToggle({ value, onChange }: PeriodToggleProps) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Chart period">
      {PERIODS.map((period) => {
        const isActive = value === period.key;
        return (
          <button
            key={period.key}
            type="button"
            onClick={() => onChange(period.key)}
            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              isActive ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'
            }`}
            aria-pressed={isActive}
          >
            {period.label}
          </button>
        );
      })}
    </div>
  );
}
