'use client';

import { useState } from 'react';

import { formatKrw } from '@/lib/format';
import type { StockSearchResult } from '@/types/dashboard';
import type { OrderRequest, OrderSide, OrderType } from '@/types/orders';

interface OrderEntryProps {
  symbol: StockSearchResult | null;
  onSubmit: (request: OrderRequest) => void;
}

const SIDES: Array<{ value: OrderSide; label: string }> = [
  { value: 'buy', label: '매수' },
  { value: 'sell', label: '매도' },
];

const ORDER_TYPES: Array<{ value: OrderType; label: string }> = [
  { value: 'limit', label: '지정가' },
  { value: 'market', label: '시장가' },
];

function sideButtonClass(value: OrderSide, isActive: boolean): string {
  if (!isActive) return 'text-gray-600 hover:text-gray-900';
  return value === 'buy'
    ? 'bg-gain text-white shadow-sm'
    : 'bg-loss text-white shadow-sm';
}

export default function OrderEntry({ symbol, onSubmit }: OrderEntryProps) {
  const [side, setSide] = useState<OrderSide>('buy');
  const [orderType, setOrderType] = useState<OrderType>('limit');
  const [quantity, setQuantity] = useState<number>(0);
  const [price, setPrice] = useState<number>(0);

  const estimatedAmount = orderType === 'market' ? 0 : quantity * price;
  // Korean stock orders are integer-share only. Reject fractional, negative,
  // or absurdly large quantities at the form boundary rather than relying
  // on the backend to 400 after the user goes through the confirm dialog.
  const MAX_QUANTITY = 1_000_000;
  const isQuantityValid =
    Number.isInteger(quantity) && quantity > 0 && quantity <= MAX_QUANTITY;
  const isPriceValid = orderType === 'market' || price > 0;
  const canSubmit = symbol !== null && isQuantityValid && isPriceValid;
  const submitButtonColorClass =
    side === 'buy' ? 'bg-gain hover:bg-gain-strong' : 'bg-loss hover:bg-loss-strong';

  const handleSubmit = () => {
    if (!canSubmit || !symbol) return;
    onSubmit({
      symbol: symbol.symbol,
      side,
      orderType,
      quantity,
      price: orderType === 'market' ? 0 : price,
    });
  };

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        handleSubmit();
      }}
    >
      <div
        className="grid grid-cols-2 gap-1 rounded-md bg-gray-100 p-1"
        role="radiogroup"
        aria-label="Order side"
      >
        {SIDES.map((option) => {
          const isActive = side === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setSide(option.value)}
              className={`rounded px-3 py-2 text-sm font-semibold transition-colors ${sideButtonClass(option.value, isActive)}`}
              role="radio"
              aria-checked={isActive}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      <div
        className="flex items-center gap-2"
        role="radiogroup"
        aria-label="Order type"
      >
        {ORDER_TYPES.map((option) => {
          const isActive = orderType === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => setOrderType(option.value)}
              className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? 'border-brand-600 bg-brand-50 text-brand-700'
                  : 'border-gray-200 bg-white text-gray-500 hover:text-gray-700'
              }`}
              role="radio"
              aria-checked={isActive}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      <label htmlFor="order-quantity" className="flex flex-col gap-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
          수량
        </span>
        <input
          id="order-quantity"
          type="number"
          min={0}
          step={1}
          value={quantity || ''}
          onChange={(event) => {
            // Clamp to non-negative integers at input time. Users can still
            // type fractional values but the form state stays integer.
            const parsed = Number.parseInt(event.target.value, 10);
            setQuantity(Number.isNaN(parsed) || parsed < 0 ? 0 : parsed);
          }}
          placeholder="0"
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-right text-sm tabular-nums text-gray-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
        />
      </label>

      <label htmlFor="order-price" className="flex flex-col gap-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
          가격 (₩){orderType === 'market' ? ' — 시장가' : ''}
        </span>
        <input
          id="order-price"
          type="number"
          min={0}
          value={price || ''}
          onChange={(event) => setPrice(Number(event.target.value) || 0)}
          placeholder={orderType === 'market' ? '시장가로 체결' : '0'}
          disabled={orderType === 'market'}
          className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-right text-sm tabular-nums text-gray-900 placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/20 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
        />
      </label>

      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>예상 체결 금액</span>
          <span className="text-base font-bold tabular-nums text-gray-900">
            {orderType === 'market' ? '시장가' : formatKrw(estimatedAmount)}
          </span>
        </div>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className={`inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${submitButtonColorClass}`}
      >
        {side === 'buy' ? '매수 주문' : '매도 주문'}
      </button>
    </form>
  );
}
