'use client';

import { useMemo } from 'react';

import type { Holding, HoldingsResult } from '@/types/portfolio';

import DegradedHoldingRow from './DegradedHoldingRow';
import HoldingRow from './HoldingRow';

type SortKey = 'name' | 'profitRate' | 'evaluationAmount';

interface HoldingsTableProps {
  data: HoldingsResult;
  sortKey: SortKey;
  sortOrder: 'asc' | 'desc';
  onSortChange: (key: SortKey) => void;
}

const HEADERS: Array<{ key: SortKey | null; label: string; align: 'left' | 'right' }> = [
  { key: 'name', label: 'Name', align: 'left' },
  { key: null, label: 'Qty', align: 'right' },
  { key: null, label: 'Avg', align: 'right' },
  { key: null, label: 'Current', align: 'right' },
  { key: 'evaluationAmount', label: 'Value', align: 'right' },
  { key: 'profitRate', label: 'P&L', align: 'right' },
];

function sortHoldings(items: Holding[], key: SortKey, order: 'asc' | 'desc'): Holding[] {
  const multiplier = order === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    if (key === 'name') return a.name.localeCompare(b.name, 'ko') * multiplier;
    if (key === 'evaluationAmount') {
      return (a.evaluationAmount - b.evaluationAmount) * multiplier;
    }
    return (a.profitRate - b.profitRate) * multiplier;
  });
}

export default function HoldingsTable({
  data,
  sortKey,
  sortOrder,
  onSortChange,
}: HoldingsTableProps) {
  const sortedHoldings = useMemo(
    () => sortHoldings(data.holdings, sortKey, sortOrder),
    [data.holdings, sortKey, sortOrder],
  );

  return (
    <table className="w-full border-collapse">
      <thead>
        <tr className="border-b border-gray-200 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          {HEADERS.map((header) => {
            const isActive = header.key !== null && sortKey === header.key;
            return (
              <th
                key={header.label}
                className={`px-4 py-3 ${header.align === 'right' ? 'text-right' : 'text-left'}`}
              >
                {header.key ? (
                  <button
                    type="button"
                    onClick={() => onSortChange(header.key as SortKey)}
                    className={`inline-flex items-center gap-1 rounded transition-colors ${
                      isActive ? 'text-gray-900' : 'text-gray-500 hover:text-gray-700'
                    }`}
                    aria-pressed={isActive}
                  >
                    {header.label}
                    {isActive ? (
                      <span aria-hidden="true">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                    ) : null}
                  </button>
                ) : (
                  header.label
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {sortedHoldings.map((holding) => (
          <HoldingRow key={holding.symbol} holding={holding} />
        ))}
        {data.errors.map((error) => (
          <DegradedHoldingRow key={error.symbol} error={error} />
        ))}
      </tbody>
    </table>
  );
}
