'use client';

import { useEffect, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import SymbolChart from '@/components/common/SymbolChart';
import { fetchAccountStatus } from '@/lib/api/auth';
import { placeOrder } from '@/lib/api/orders';
import type { StockSearchResult } from '@/types/dashboard';
import type { OrderRequest } from '@/types/orders';

import OrderConfirmDialog from './OrderConfirmDialog';
import OrderEntry from './OrderEntry';
import OrderHistory from './OrderHistory';
import SymbolPicker from './SymbolPicker';
import TradingWatchlist from './TradingWatchlist';

interface Toast {
  kind: 'success' | 'error';
  message: string;
}

// Toast lifetime. Errors linger longer than successes so the user has
// time to read a failure reason before it disappears.
const TOAST_SUCCESS_MS = 5_000;
const TOAST_ERROR_MS = 10_000;

// Glue component that holds the shared trading state (selected symbol,
// pending confirmation, submit mutation) and wires the sub-components
// together. Also owns the shared toast region so place-order and cancel
// results feed into the same status surface.
export default function TradingWorkspace() {
  const queryClient = useQueryClient();
  const [selectedSymbol, setSelectedSymbol] = useState<StockSearchResult | null>(null);
  // Pre-fill the symbol search when arriving from the chart modal's 주문하기
  // action (`/trading?symbol=...`). Read once on mount to avoid pulling in a
  // useSearchParams Suspense boundary for a transient nav param.
  const [initialSymbol] = useState(() =>
    typeof window === 'undefined'
      ? ''
      : (new URLSearchParams(window.location.search).get('symbol') ?? ''),
  );
  const [pendingRequest, setPendingRequest] = useState<OrderRequest | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);

  const { data: authData } = useQuery({
    queryKey: ['auth', 'status'],
    queryFn: fetchAccountStatus,
    refetchInterval: 60_000,
  });

  const placeOrderMutation = useMutation({
    mutationFn: placeOrder,
    onSuccess: (order) => {
      queryClient.invalidateQueries({ queryKey: ['orders'] });
      setToast({
        kind: 'success',
        message: `주문 제출 완료 — ${order.name} ${order.quantity}주`,
      });
      setPendingRequest(null);
    },
    onError: (error) => {
      setToast({
        kind: 'error',
        message: error instanceof Error ? error.message : '주문 제출 실패',
      });
    },
  });

  // Auto-dismiss toasts. Cleared on unmount / replacement. Spec §11 requires
  // toast auto-dismiss so stale success banners can't mislead a user who
  // walks away from the tab.
  useEffect(() => {
    if (!toast) return undefined;
    const timeout = toast.kind === 'error' ? TOAST_ERROR_MS : TOAST_SUCCESS_MS;
    const id = window.setTimeout(() => setToast(null), timeout);
    return () => window.clearTimeout(id);
  }, [toast]);

  const handleConfirm = () => {
    if (!pendingRequest) return;
    placeOrderMutation.mutate(pendingRequest);
  };

  return (
    <>
      {toast ? (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            toast.kind === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border-amber-200 bg-amber-50 text-amber-800'
          }`}
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center justify-between">
            <span>{toast.message}</span>
            <button
              type="button"
              onClick={() => setToast(null)}
              className="rounded p-1 text-xs font-semibold text-gray-500 hover:bg-white/60"
              aria-label="Dismiss notification"
            >
              ✕
            </button>
          </div>
        </div>
      ) : null}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        {/* Left rail: symbol search + watchlist — both select the symbol that
            drives the inline chart and order entry. No modal on this page. */}
        <div className="flex flex-col gap-6">
          <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-card">
            <header className="mb-4">
              <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
                Symbol
              </h2>
            </header>
            <SymbolPicker
              selected={selectedSymbol}
              onSelect={setSelectedSymbol}
              initialQuery={initialSymbol}
            />
          </article>

          <TradingWatchlist
            selectedSymbol={selectedSymbol?.symbol ?? null}
            onSelect={setSelectedSymbol}
          />
        </div>

        {/* Main column: inline chart for the selected symbol + order entry. */}
        <div className="flex flex-col gap-6">
          <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-card">
            {selectedSymbol ? (
              <SymbolChart symbol={selectedSymbol.symbol} name={selectedSymbol.name} />
            ) : (
              <div className="flex h-96 items-center justify-center text-sm text-gray-400">
                종목을 검색하거나 관심종목에서 선택하면 차트가 표시됩니다.
              </div>
            )}
          </article>

          <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-card">
            <header className="mb-4">
              <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
                Order Entry
              </h2>
            </header>
            <OrderEntry
              symbol={selectedSymbol}
              onSubmit={(request) => {
                setToast(null);
                setPendingRequest(request);
              }}
            />
          </article>
        </div>
      </section>

      <section>
        <OrderHistory
          onCancelSuccess={(id) =>
            setToast({ kind: 'success', message: `주문 #${id} 취소 완료` })
          }
          onCancelError={(error) =>
            setToast({
              kind: 'error',
              message: `취소 실패 — ${error.message}`,
            })
          }
        />
      </section>

      <OrderConfirmDialog
        request={pendingRequest}
        symbolName={selectedSymbol?.name ?? ''}
        mode={authData?.accountMode}
        isSubmitting={placeOrderMutation.isPending}
        onConfirm={handleConfirm}
        onCancel={() => setPendingRequest(null)}
      />
    </>
  );
}
