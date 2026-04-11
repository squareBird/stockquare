'use client';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PriceDisplay from '@/components/common/PriceDisplay';
import type { WatchlistItem as WatchlistItemType } from '@/types/dashboard';

interface WatchlistItemProps {
  item: WatchlistItemType;
  onRemove: (id: number) => void;
}

export default function WatchlistItem({ item, onRemove }: WatchlistItemProps) {
  return (
    <li className="group flex items-center justify-between gap-4 border-b border-gray-100 px-5 py-3 transition-colors last:border-b-0 hover:bg-gray-50">
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="truncate font-medium text-gray-900">{item.name}</span>
          <span className="font-mono text-xs text-gray-400">{item.symbol}</span>
        </div>
      </div>

      <div className="flex flex-col items-end gap-0.5">
        <PriceDisplay value={item.price} className="text-sm font-medium tabular-nums text-gray-900" />
        <ChangeDisplay amount={item.change} rate={item.changeRate} className="text-xs" />
      </div>

      <button
        type="button"
        onClick={() => onRemove(item.id)}
        className="rounded p-1 text-gray-300 transition-opacity hover:bg-gray-100 hover:text-gray-600 md:opacity-0 md:group-hover:opacity-100"
        aria-label={`Remove ${item.name} from watchlist`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
        </svg>
      </button>
    </li>
  );
}
