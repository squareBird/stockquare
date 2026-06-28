'use client';

import { useEffect, useRef, useState } from 'react';

import { formatKrw, formatVolume } from '@/lib/format';
import type { AccountMode } from '@/types/dashboard';
import type { OrderRequest } from '@/types/orders';

interface OrderConfirmDialogProps {
  request: OrderRequest | null;
  symbolName: string;
  mode: AccountMode | undefined;
  isSubmitting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Two-step confirmation dialog. The user opens it from OrderEntry, reviews
// the order details (step 1), and must click Confirm again (step 2) to
// actually submit. Each step has distinct copy so the user never accidentally
// fires an order by clicking the same button twice.
export default function OrderConfirmDialog({
  request,
  symbolName,
  mode,
  isSubmitting,
  onConfirm,
  onCancel,
}: OrderConfirmDialogProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  // Reset to step 1 every time the dialog reopens for a new request. `request`
  // is a fresh object per open, so comparing identity during render lets us
  // reset without a sync effect.
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  const [confirmedRequest, setConfirmedRequest] = useState<OrderRequest | null>(request);
  if (request !== confirmedRequest) {
    setConfirmedRequest(request);
    setStep(1);
  }

  useEffect(() => {
    if (!request) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [request, onCancel]);

  // Move initial focus to the safe "취소" action so a stray Enter press
  // from the form never fires an immediate submit. A proper focus trap
  // (Tab cycling) is a follow-up — Escape + explicit button focus is
  // sufficient for the immediate safety gap.
  useEffect(() => {
    if (request) cancelButtonRef.current?.focus();
  }, [request]);

  if (!request) return null;

  const estimatedAmount = request.orderType === 'market' ? 0 : request.quantity * request.price;
  const sideLabel = request.side === 'buy' ? '매수' : '매도';
  const sideColor = request.side === 'buy' ? 'text-gain-strong' : 'text-loss-strong';
  const typeLabel = request.orderType === 'market' ? '시장가' : '지정가';

  let submitLabel: string;
  if (isSubmitting) submitLabel = '제출 중…';
  else if (step === 1) submitLabel = '다음';
  else submitLabel = '주문 제출';

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 md:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Order confirmation"
    >
      <button
        type="button"
        className="absolute inset-0 h-full w-full cursor-default"
        onClick={onCancel}
        tabIndex={-1}
        aria-hidden="true"
      />

      <div className="relative z-10 w-full max-w-md rounded-t-2xl bg-white p-5 shadow-elevated md:rounded-2xl">
        <header className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {step === 1 ? '주문 확인' : '최종 확인'}
          </h2>
          {mode === 'real' ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-surface-inverse px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-white">
              <span className="h-1.5 w-1.5 rounded-full bg-gain" aria-hidden="true" />
              REAL
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full border border-dashed border-gray-300 bg-gray-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-gray-500">
              MOCK
            </span>
          )}
        </header>

        <dl className="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm">
          <div className="flex items-baseline justify-between">
            <dt className="text-gray-500">종목</dt>
            <dd className="text-right">
              <div className="font-medium text-gray-900">{symbolName}</div>
              <div className="font-mono text-xs text-gray-400">{request.symbol}</div>
            </dd>
          </div>
          <div className="flex items-baseline justify-between">
            <dt className="text-gray-500">주문 종류</dt>
            <dd className={`font-semibold ${sideColor}`}>
              {sideLabel} · {typeLabel}
            </dd>
          </div>
          <div className="flex items-baseline justify-between">
            <dt className="text-gray-500">수량</dt>
            <dd className="font-medium tabular-nums text-gray-900">
              {formatVolume(request.quantity)}
            </dd>
          </div>
          <div className="flex items-baseline justify-between">
            <dt className="text-gray-500">가격</dt>
            <dd className="font-medium tabular-nums text-gray-900">
              {request.orderType === 'market' ? '시장가' : formatKrw(request.price)}
            </dd>
          </div>
          <div className="flex items-baseline justify-between border-t border-gray-200 pt-2">
            <dt className="font-semibold text-gray-700">예상 체결 금액</dt>
            <dd className="text-base font-bold tabular-nums text-gray-900">
              {request.orderType === 'market' ? '시장가' : formatKrw(estimatedAmount)}
            </dd>
          </div>
        </dl>

        {step === 2 ? (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            한 번 더 확인하세요. {mode === 'real' ? '실제 주문이 체결됩니다.' : '모의 주문이 기록됩니다.'}
          </p>
        ) : null}

        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            ref={cancelButtonRef}
            type="button"
            onClick={onCancel}
            className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
            disabled={isSubmitting}
          >
            취소
          </button>
          <button
            type="button"
            onClick={() => {
              if (step === 1) {
                setStep(2);
                return;
              }
              onConfirm();
            }}
            disabled={isSubmitting}
            className="inline-flex items-center justify-center rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
