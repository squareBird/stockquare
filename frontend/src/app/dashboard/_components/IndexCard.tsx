import ChangeDisplay from '@/components/common/ChangeDisplay';
import { formatIndexValue } from '@/lib/format';
import type { MarketIndex } from '@/types/dashboard';

interface IndexCardProps {
  index: MarketIndex;
}

const STATUS_COLOR_MAP = {
  open: 'text-emerald-500',
  closed: 'text-gray-400',
  pre_market: 'text-amber-500',
} as const;

const STATUS_LABEL_MAP = {
  open: 'OPEN',
  closed: 'CLOSED',
  pre_market: 'PRE',
} as const;

export default function IndexCard({ index }: IndexCardProps) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold text-gray-700">{index.name}</span>
        <span className={`text-[10px] font-semibold uppercase ${STATUS_COLOR_MAP[index.status]}`}>
          {STATUS_LABEL_MAP[index.status]}
        </span>
      </div>
      <div className="mt-2 text-xl font-bold tabular-nums tracking-tight text-gray-900">
        {formatIndexValue(index.value)}
      </div>
      <div className="mt-1 text-sm">
        <ChangeDisplay amount={index.change} rate={index.changeRate} currency={false} />
      </div>
    </div>
  );
}
