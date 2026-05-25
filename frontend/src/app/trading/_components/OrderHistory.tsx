'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import StaleBadge from '@/components/common/StaleBadge';
import { cancelOrder, fetchOrders } from '@/lib/api/orders';

import OrderRow from './OrderRow';

const ORDERS_QUERY_KEY = ['orders'] as const;

interface OrderHistoryProps {
  onCancelSuccess?: (id: number) => void;
  onCancelError?: (error: Error) => void;
}

export default function OrderHistory({ onCancelSuccess, onCancelError }: OrderHistoryProps) {
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ORDERS_QUERY_KEY,
    queryFn: fetchOrders,
    // Per TRADING.md §6 — poll faster than market-hours default so fills
    // and broker-side cancels surface within 15s.
    refetchInterval: 15_000,
    // Order state changes (fills, broker cancels) are the one thing we want
    // up to date the instant the user focuses the tab. Overrides the global
    // `refetchOnWindowFocus: false` default in `query-client.ts`.
    refetchOnWindowFocus: 'always',
  });

  const cancelMutation = useMutation({
    mutationFn: cancelOrder,
    onSuccess: (_result, id) => {
      queryClient.invalidateQueries({ queryKey: ORDERS_QUERY_KEY });
      onCancelSuccess?.(id);
    },
    onError: (error) => {
      onCancelError?.(error instanceof Error ? error : new Error(String(error)));
    },
  });

  const showStaleBadge = Boolean(data) && isError;
  const showFullError = !data && isError;

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-card">
      <header className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold tracking-tight text-gray-900">Order History</h2>
          {showStaleBadge ? <StaleBadge /> : null}
        </div>
        {data ? (
          <span className="text-xs text-gray-500">총 {data.count}건</span>
        ) : null}
      </header>

      {isLoading ? (
        <div className="space-y-2 p-5">
          <div className="h-12 animate-pulse rounded bg-gray-100" />
          <div className="h-12 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {showFullError ? (
        <p className="p-5 text-sm text-gain-strong">Failed to load orders.</p>
      ) : null}

      {!showFullError && data && data.orders.length === 0 ? (
        <p className="p-8 text-center text-sm text-gray-400">
          주문 내역이 없습니다. 위에서 첫 주문을 제출해 보세요.
        </p>
      ) : null}

      {data && data.orders.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b border-gray-200 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Side</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Price</th>
                <th className="px-4 py-3 text-right">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.orders.map((order) => (
                <OrderRow
                  key={order.id}
                  order={order}
                  onCancel={(id) => cancelMutation.mutate(id)}
                  isCancelling={
                    cancelMutation.isPending && cancelMutation.variables === order.id
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </article>
  );
}
