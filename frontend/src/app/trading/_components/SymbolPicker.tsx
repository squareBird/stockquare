'use client';

import { useEffect, useMemo, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { searchStocks } from '@/lib/api/stocks';
import type { StockSearchResult } from '@/types/dashboard';

interface SymbolPickerProps {
  selected: StockSearchResult | null;
  onSelect: (stock: StockSearchResult) => void;
  // Seeds the search box (e.g. when arriving from the chart modal's 주문하기
  // action with `?symbol=` in the URL).
  initialQuery?: string;
}

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export default function SymbolPicker({ selected, onSelect, initialQuery }: SymbolPickerProps) {
  const [query, setQuery] = useState(initialQuery ?? '');
  const debouncedQuery = useDebouncedValue(query, 300);
  const enabled = useMemo(() => debouncedQuery.trim().length > 0, [debouncedQuery]);

  const { data, isFetching } = useQuery({
    queryKey: ['stocks', 'search', debouncedQuery],
    queryFn: () => searchStocks(debouncedQuery),
    enabled,
  });

  return (
    <div className="flex flex-col gap-3">
      <input
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="종목 검색 (심볼 또는 이름)"
        className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
        aria-label="Stock symbol or name search"
      />

      {selected ? (
        <div className="rounded-lg border border-brand-200 bg-brand-50 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-brand-700">
            Selected
          </div>
          <div className="mt-1 flex items-baseline justify-between gap-2">
            <span className="font-semibold text-gray-900">{selected.name}</span>
            <span className="font-mono text-xs text-gray-500">
              {selected.symbol} · {selected.market}
            </span>
          </div>
        </div>
      ) : null}

      <div className="max-h-72 overflow-y-auto rounded-lg border border-gray-200 bg-white">
        {!enabled ? (
          <p className="py-8 text-center text-sm text-gray-400">
            종목을 검색해 선택하세요.
          </p>
        ) : null}

        {enabled && isFetching ? (
          <p className="py-8 text-center text-sm text-gray-400">Searching…</p>
        ) : null}

        {enabled && !isFetching && data && data.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">No matching stocks.</p>
        ) : null}

        {data && data.length > 0 ? (
          <ul className="divide-y divide-gray-100">
            {data.map((stock) => {
              const isSelected = selected?.symbol === stock.symbol;
              return (
                <li key={stock.symbol}>
                  {/* Selecting a result drives the inline chart + order entry
                      (no modal on the Trading page). */}
                  <button
                    type="button"
                    onClick={() => onSelect(stock)}
                    className={`flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors ${
                      isSelected ? 'bg-brand-50' : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-gray-900">{stock.name}</div>
                      <div className="font-mono text-xs text-gray-400">
                        {stock.symbol} · {stock.market}
                      </div>
                    </div>
                    {isSelected ? (
                      <span className="shrink-0 text-xs font-semibold text-brand-700">✓ Selected</span>
                    ) : (
                      <span className="shrink-0 text-xs font-medium text-gray-500">Select</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
