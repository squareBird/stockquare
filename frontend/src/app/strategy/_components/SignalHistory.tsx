'use client';

import { useQuery } from '@tanstack/react-query';

import SignalBadge from '@/components/common/SignalBadge';
import { fetchSignals } from '@/lib/api/strategy';

interface SignalHistoryProps {
  strategyId: number;
}

function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return '방금 전';
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}시간 전`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}일 전`;
}

export default function SignalHistory({ strategyId }: SignalHistoryProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['strategies', strategyId, 'signals'],
    queryFn: () => fetchSignals(strategyId),
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        <div className="h-8 animate-pulse rounded bg-gray-100" />
        <div className="h-8 animate-pulse rounded bg-gray-100" />
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-red-500">신호 내역을 불러올 수 없습니다.</p>;
  }

  if (!data || data.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-gray-400">
        아직 평가 신호가 없습니다.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-[11px] font-semibold uppercase tracking-widest text-gray-500">
            <th className="py-2 pr-4">신호</th>
            <th className="py-2 pr-4">신뢰도</th>
            <th className="py-2 pr-4 hidden sm:table-cell">근거</th>
            <th className="py-2 pr-4">시간</th>
            <th className="py-2">체결</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {data.map((signal, idx) => (
            // Signals have no stable id from the API; use index as key (list is immutable display)
            <tr key={idx} className="align-top">
              <td className="py-2 pr-4">
                <SignalBadge action={signal.action} />
              </td>
              <td className="py-2 pr-4 tabular-nums text-gray-700">
                {(signal.confidence * 100).toFixed(0)}%
              </td>
              <td className="py-2 pr-4 hidden max-w-xs truncate text-gray-500 sm:table-cell">
                {signal.rationale}
              </td>
              <td className="py-2 pr-4 whitespace-nowrap text-gray-400">
                {formatRelativeTime(signal.createdAt)}
              </td>
              <td className="py-2 text-gray-400">
                {signal.executed ? (
                  <span className="text-emerald-600">완료</span>
                ) : (
                  <span>-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
