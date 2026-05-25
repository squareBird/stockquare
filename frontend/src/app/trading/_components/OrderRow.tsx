'use client';

import { useEffect, useState } from 'react';

import { formatKrw, formatVolume } from '@/lib/format';
import type { Order, OrderStatus } from '@/types/orders';

interface OrderRowProps {
  order: Order;
  onCancel: (id: number) => void;
  isCancelling: boolean;
}

const STATUS_LABEL_MAP: Record<OrderStatus, string> = {
  pending: '대기',
  accepted: '접수',
  partially_filled: '부분체결',
  filled: '체결',
  cancelled: '취소',
  rejected: '거부',
};

const STATUS_CLASS_MAP: Record<OrderStatus, string> = {
  pending: 'bg-gray-100 text-gray-600',
  accepted: 'bg-brand-50 text-brand-700',
  partially_filled: 'bg-brand-50 text-brand-700',
  filled: 'bg-emerald-50 text-emerald-700',
  cancelled: 'bg-gray-100 text-gray-500',
  rejected: 'bg-amber-50 text-amber-700',
};

// Inline two-step cancel: first click arms the button, second click fires
// the mutation. Arm state times out after 4 seconds so a stale armed state
// can't be triggered by a late enter-key repeat. Avoids a separate modal
// while still making cancel symmetric with the two-step place-order flow.
const ARM_TIMEOUT_MS = 4_000;

export default function OrderRow({ order, onCancel, isCancelling }: OrderRowProps) {
  const isCancellable = order.status === 'pending' || order.status === 'accepted';
  const sideLabel = order.side === 'buy' ? '매수' : '매도';
  const sideColor = order.side === 'buy' ? 'text-gain-strong' : 'text-loss-strong';

  const [isArmed, setIsArmed] = useState(false);

  useEffect(() => {
    if (!isArmed) return undefined;
    const id = window.setTimeout(() => setIsArmed(false), ARM_TIMEOUT_MS);
    return () => window.clearTimeout(id);
  }, [isArmed]);

  const handleCancelClick = () => {
    if (isCancelling) return;
    if (!isArmed) {
      setIsArmed(true);
      return;
    }
    setIsArmed(false);
    onCancel(order.id);
  };

  let cancelLabel: string;
  if (isCancelling) cancelLabel = '취소 중…';
  else if (isArmed) cancelLabel = '정말 취소?';
  else cancelLabel = '취소';

  return (
    <tr className="border-b border-gray-100 transition-colors last:border-b-0 hover:bg-gray-50">
      <td className="px-4 py-3">
        <div className="flex flex-col">
          <span className="font-medium text-gray-900">{order.name}</span>
          <span className="font-mono text-xs text-gray-400">{order.symbol}</span>
        </div>
      </td>
      <td className={`px-4 py-3 text-sm font-semibold ${sideColor}`}>
        {sideLabel}
        <span className="ml-1 text-[10px] font-normal uppercase tracking-widest text-gray-400">
          {order.orderType === 'market' ? 'MKT' : 'LMT'}
        </span>
      </td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-700">
        {formatVolume(order.quantity)}
      </td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-700">
        {order.orderType === 'market' ? '시장가' : formatKrw(order.price)}
      </td>
      <td className="px-4 py-3 text-right">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest ${STATUS_CLASS_MAP[order.status]}`}
        >
          {STATUS_LABEL_MAP[order.status]}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        {isCancellable ? (
          <button
            type="button"
            onClick={handleCancelClick}
            disabled={isCancelling}
            className={`inline-flex items-center justify-center rounded-md px-2 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              isArmed
                ? 'border border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100'
                : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-100'
            }`}
            aria-pressed={isArmed}
          >
            {cancelLabel}
          </button>
        ) : (
          <span className="text-xs text-gray-300">—</span>
        )}
      </td>
    </tr>
  );
}
