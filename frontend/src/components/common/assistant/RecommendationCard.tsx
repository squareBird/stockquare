'use client';

import PriceDisplay from '@/components/common/PriceDisplay';
import { changeColorClass, formatSignedPercent } from '@/lib/format';
import { useStockDetail } from '@/stores/stock-detail';
import type { Recommendation } from '@/types/assistant';

interface RecommendationCardProps {
  recommendation: Recommendation;
  // Seeds a follow-up turn (e.g. "관심종목에 추가") prefilled in the composer.
  onAddToWatchlist: (rec: Recommendation) => void;
}

export default function RecommendationCard({
  recommendation,
  onAddToWatchlist,
}: RecommendationCardProps) {
  const openDetail = useStockDetail((s) => s.open);
  const { symbol, name, price, changeRate, reason } = recommendation;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => openDetail(symbol, name)}
          className="text-left font-medium text-gray-900 hover:text-brand-600"
        >
          {name} <span className="text-xs text-gray-400">{symbol}</span>
        </button>
        {typeof price === 'number' ? <PriceDisplay value={price} /> : null}
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="text-xs text-gray-500">{reason}</span>
        {typeof changeRate === 'number' ? (
          <span className={`text-xs tabular-nums ${changeColorClass(changeRate)}`}>
            {formatSignedPercent(changeRate)}
          </span>
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => onAddToWatchlist(recommendation)}
        className="mt-2 w-full rounded-md bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-200"
      >
        관심종목 추가
      </button>
    </div>
  );
}
