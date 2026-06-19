'use client';

import { useEffect } from 'react';

import { useRouter } from 'next/navigation';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import SymbolChart from '@/components/common/SymbolChart';
import { addWatchlistItem } from '@/lib/api/watchlist';
import { useStockDetail } from '@/stores/stock-detail';

export default function StockDetailModal() {
  const activeSymbol = useStockDetail((state) => state.activeSymbol);
  const activeName = useStockDetail((state) => state.activeName);
  const close = useStockDetail((state) => state.close);
  const router = useRouter();
  const queryClient = useQueryClient();

  const isOpen = activeSymbol !== null;
  // Phase 1 watchlist + trading are KR-only (domestic KIS endpoints, KRW).
  // Overseas symbols are searchable for discovery but their quick actions
  // would be rejected, so they are disabled with a note instead.
  const isKrSymbol = activeSymbol !== null && /^\d{6}$/.test(activeSymbol);

  // Quick action: add the open symbol to the watchlist. Mirrors the dashboard
  // add flow (invalidate ['watchlist'] so the enriched row reloads).
  const addMutation = useMutation({
    mutationFn: addWatchlistItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  });
  const resetAdd = addMutation.reset;

  // Reset the add state when a different symbol opens so the button never shows
  // a stale "추가됨" carried over from the previously viewed stock.
  useEffect(() => {
    resetAdd();
  }, [activeSymbol, resetAdd]);

  const handleAddWatchlist = () => {
    if (activeSymbol) addMutation.mutate(activeSymbol);
  };

  // Quick action: jump to the order page. The symbol rides along as a query
  // param so the trading SymbolPicker can pre-fill its search.
  const handleOrder = () => {
    if (!activeSymbol) return;
    router.push(`/trading?symbol=${activeSymbol}`);
    close();
  };

  // Dismiss on Escape so keyboard users can always close the modal.
  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, close]);

  if (!isOpen || activeSymbol === null) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 md:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={`${activeName ?? activeSymbol} price chart`}
    >
      {/*
        The backdrop is a button hidden from the accessibility tree
        (aria-hidden + tabIndex -1). Keyboard users dismiss via Escape or the
        visible "Close" button, matching the AddStockModal pattern.
      */}
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default"
        onClick={close}
        tabIndex={-1}
        aria-hidden="true"
      />

      <div className="relative z-10 w-full max-w-2xl rounded-t-2xl bg-white p-5 shadow-xl md:rounded-2xl">
        <SymbolChart
          symbol={activeSymbol}
          name={activeName}
          headerRight={
            <button
              type="button"
              onClick={close}
              className="rounded p-1 text-sm text-gray-500 hover:bg-gray-100"
              aria-label="Close"
            >
              Close
            </button>
          }
        />

        {isKrSymbol ? (
          <>
            <div className="mt-5 flex gap-2">
              <button
                type="button"
                onClick={handleAddWatchlist}
                disabled={addMutation.isPending || addMutation.isSuccess}
                className="flex-1 rounded-md bg-gray-100 px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-200 disabled:cursor-default disabled:opacity-60"
              >
                {addMutation.isSuccess
                  ? '관심종목에 추가됨'
                  : addMutation.isPending
                    ? '추가 중…'
                    : '관심종목 추가'}
              </button>
              <button
                type="button"
                onClick={handleOrder}
                className="flex-1 rounded-md bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-700"
              >
                주문하기 →
              </button>
            </div>

            {addMutation.isError ? (
              <p className="mt-2 text-right text-xs text-red-500" role="status" aria-live="polite">
                관심종목 추가에 실패했습니다.
              </p>
            ) : null}
          </>
        ) : (
          <p className="mt-5 text-center text-xs text-gray-400">
            해외 종목의 관심종목·주문은 아직 지원하지 않습니다 (국내 종목만 가능).
          </p>
        )}
      </div>
    </div>
  );
}
