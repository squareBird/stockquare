'use client';

import { useQuery } from '@tanstack/react-query';

import SignalBadge from '@/components/common/SignalBadge';
import { fetchStrategies } from '@/lib/api/strategy';

interface StrategyListProps {
  selectedId: number | null;
  onSelect: (id: number) => void;
  onEdit: (id: number) => void;
}

const EXECUTION_MODE_LABEL: Record<string, string> = {
  signal_only: '신호전용',
  auto: '자동',
};

export default function StrategyList({ selectedId, onSelect, onEdit }: StrategyListProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
  });

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-card">
      <header className="border-b border-gray-100 px-4 py-3">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500">
          전략 목록
        </h2>
      </header>

      {isLoading ? (
        <div className="space-y-2 p-4">
          <div className="h-14 animate-pulse rounded bg-gray-100" />
          <div className="h-14 animate-pulse rounded bg-gray-100" />
        </div>
      ) : null}

      {!isLoading && isError ? (
        <p className="p-4 text-sm text-red-500">전략 목록을 불러올 수 없습니다.</p>
      ) : null}

      {!isLoading && !isError && data && data.strategies.length === 0 ? (
        <p className="p-6 text-center text-sm text-gray-400">
          아직 전략이 없습니다. + 새 전략을 눌러 만드세요.
        </p>
      ) : null}

      {data && data.strategies.length > 0 ? (
        <ul>
          {data.strategies.map((strategy) => {
            const isActive = strategy.id === selectedId;
            return (
              <li key={strategy.id}>
                <button
                  type="button"
                  onClick={() => onSelect(strategy.id)}
                  className={`flex w-full flex-col gap-1.5 border-b border-gray-100 px-4 py-3 text-left transition-colors last:border-b-0 ${
                    isActive ? 'bg-brand-50' : 'hover:bg-gray-50'
                  }`}
                  aria-pressed={isActive}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-gray-900">
                        {strategy.name}
                      </div>
                      <div className="font-mono text-xs text-gray-400">
                        {strategy.symbol} · {strategy.strategyType}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEdit(strategy.id);
                      }}
                      className="shrink-0 rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-gray-200 hover:text-gray-700"
                      aria-label={`Edit ${strategy.name}`}
                    >
                      편집
                    </button>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                      ● {EXECUTION_MODE_LABEL[strategy.executionMode] ?? strategy.executionMode}
                    </span>
                    {strategy.lastSignal ? (
                      <span className="flex items-center gap-1 text-[10px] text-gray-400">
                        최근: <SignalBadge action={strategy.lastSignal.action} />
                      </span>
                    ) : (
                      <span className="text-[10px] text-gray-400">평가 전</span>
                    )}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </article>
  );
}
