'use client';

import { useEffect, useMemo, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { searchStocks } from '@/lib/api/stocks';
import { useStockDetail } from '@/stores/stock-detail';

interface AddStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (symbol: string) => void;
}

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export default function AddStockModal({ isOpen, onClose, onAdd }: AddStockModalProps) {
  const openDetail = useStockDetail((state) => state.open);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncedValue(query, 300);

  const enabled = useMemo(() => debouncedQuery.trim().length > 0, [debouncedQuery]);

  const { data, isFetching } = useQuery({
    queryKey: ['stocks', 'search', debouncedQuery],
    queryFn: () => searchStocks(debouncedQuery),
    enabled: isOpen && enabled,
  });

  // Reset input whenever the modal is reopened.
  useEffect(() => {
    if (!isOpen) setQuery('');
  }, [isOpen]);

  // Dismiss on Escape so keyboard users can always close the modal.
  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 md:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Add stock to watchlist"
    >
      {/*
        The backdrop is a button that is hidden from the accessibility tree
        (aria-hidden + tabIndex -1). Keyboard users dismiss via Escape or the
        visible "Close" button inside the dialog.
      */}
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default"
        onClick={onClose}
        tabIndex={-1}
        aria-hidden="true"
      />

      <div className="relative z-10 w-full max-w-md rounded-t-2xl bg-white p-5 shadow-xl md:rounded-2xl">
        <header className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Add Stock</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-sm text-gray-500 hover:bg-gray-100"
            aria-label="Close"
          >
            Close
          </button>
        </header>

        <input
          type="text"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by symbol or name (e.g. 005930, Samsung)"
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-gray-400 focus:ring-1 focus:ring-gray-300"
        />

        <div className="mt-3 max-h-64 overflow-y-auto">
          {!enabled ? (
            <p className="py-6 text-center text-sm text-gray-400">Type to search stocks.</p>
          ) : null}

          {enabled && isFetching ? (
            <p className="py-6 text-center text-sm text-gray-400">Searching…</p>
          ) : null}

          {enabled && !isFetching && data && data.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-400">No matching stocks.</p>
          ) : null}

          {data && data.length > 0 ? (
            <ul className="divide-y divide-gray-100">
              {data.map((stock) => (
                <li
                  key={stock.symbol}
                  className="flex items-center justify-between gap-2 px-2 py-3 hover:bg-gray-50"
                >
                  {/* Name/symbol opens the chart modal; the trailing button keeps
                      the primary add-to-watchlist action. */}
                  <button
                    type="button"
                    onClick={() => openDetail(stock.symbol, stock.name)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="text-sm font-medium text-gray-900 hover:underline">
                      {stock.name}
                    </div>
                    <div className="text-xs text-gray-400">
                      {stock.symbol} · {stock.market}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onAdd(stock.symbol);
                      onClose();
                    }}
                    className="shrink-0 rounded px-2 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-100"
                  >
                    Add
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </div>
  );
}
