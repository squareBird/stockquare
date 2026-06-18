'use client';

import ChangeDisplay from '@/components/common/ChangeDisplay';
import PriceDisplay from '@/components/common/PriceDisplay';
import { formatKrw, formatVolume } from '@/lib/format';
import { useStockDetail } from '@/stores/stock-detail';
import type { Holding } from '@/types/portfolio';

interface HoldingRowProps {
  holding: Holding;
}

export default function HoldingRow({ holding }: HoldingRowProps) {
  const openDetail = useStockDetail((state) => state.open);
  return (
    <tr className="border-b border-gray-100 transition-colors last:border-b-0 hover:bg-gray-50">
      <td className="px-4 py-3">
        <button
          type="button"
          onClick={() => openDetail(holding.symbol, holding.name)}
          className="flex flex-col text-left"
        >
          <span className="font-medium text-gray-900 hover:underline">{holding.name}</span>
          <span className="font-mono text-xs text-gray-400">{holding.symbol}</span>
        </button>
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-gray-700">
        {formatVolume(holding.quantity)}
      </td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-700">
        {formatKrw(holding.avgPurchasePrice)}
      </td>
      <td className="px-4 py-3 text-right text-sm tabular-nums text-gray-900">
        {formatKrw(holding.currentPrice)}
      </td>
      <td className="px-4 py-3 text-right text-sm font-medium tabular-nums text-gray-900">
        <PriceDisplay value={holding.evaluationAmount} />
      </td>
      <td className="px-4 py-3 text-right">
        <ChangeDisplay amount={holding.profit} rate={holding.profitRate} className="text-sm" />
      </td>
    </tr>
  );
}
