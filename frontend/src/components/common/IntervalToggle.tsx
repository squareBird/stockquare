'use client';

import type { ChartInterval } from '@/types/charts';

interface IntervalToggleProps {
  value: ChartInterval;
  onChange: (interval: ChartInterval) => void;
}

// Candle granularity, not a lookback window: 분봉 / 일봉(기본) / 주봉 / 월봉.
const INTERVALS: Array<{ key: ChartInterval; label: string }> = [
  { key: 'min', label: '분봉' },
  { key: 'day', label: '일봉' },
  { key: 'week', label: '주봉' },
  { key: 'month', label: '월봉' },
];

export default function IntervalToggle({ value, onChange }: IntervalToggleProps) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Chart interval">
      {INTERVALS.map((interval) => {
        const isActive = value === interval.key;
        return (
          <button
            key={interval.key}
            type="button"
            onClick={() => onChange(interval.key)}
            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              isActive ? 'bg-gray-900 text-white' : 'text-gray-500 hover:bg-gray-100'
            }`}
            aria-pressed={isActive}
          >
            {interval.label}
          </button>
        );
      })}
    </div>
  );
}
