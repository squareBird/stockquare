'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import SignalBadge from '@/components/common/SignalBadge';
import { deleteStrategy, evaluateStrategy, fetchStrategies } from '@/lib/api/strategy';
import type { Indicator, Signal } from '@/types/strategy';

import SignalHistory from './SignalHistory';

interface StrategyDetailProps {
  strategyId: number;
  onDeleted: () => void;
  onEdit: (id: number) => void;
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

function IndicatorSummary({ indicators }: { indicators: Indicator[] }) {
  return (
    <ul className="space-y-1">
      {indicators.map((ind, idx) => {
        let description = '';
        if (ind.kind === 'ma_cross') {
          description = `MA 골든크로스 — 빠른 이동평균 ${ind.fast}일 / 느린 이동평균 ${ind.slow}일`;
        } else if (ind.kind === 'rsi') {
          description = `RSI(${ind.period}) — 과매도 ${ind.oversold} / 과매수 ${ind.overbought}`;
        } else if (ind.kind === 'bollinger') {
          description = `볼린저밴드 — 기간 ${ind.period}일, 배수 ${ind.mult}`;
        } else {
          description = ind.kind;
        }
        return (
          // Indicator list index is stable display-only; using idx as key is safe
          <li key={idx} className="flex items-center gap-2 text-sm text-gray-700">
            <span className="text-gray-400">•</span>
            {description}
          </li>
        );
      })}
    </ul>
  );
}

function LatestSignalCard({ signal }: { signal: Signal }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <div className="mb-2 flex items-center gap-3">
        <SignalBadge action={signal.action} className="text-sm" />
        <span className="text-sm font-medium text-gray-700">
          신뢰도 {(signal.confidence * 100).toFixed(0)}%
        </span>
        <span className="text-xs text-gray-400">{formatRelativeTime(signal.createdAt)}</span>
      </div>
      <p className="text-sm text-gray-500">{signal.rationale}</p>
    </div>
  );
}

export default function StrategyDetail({ strategyId, onDeleted, onEdit }: StrategyDetailProps) {
  const queryClient = useQueryClient();

  const { data: strategiesData, isLoading, isError } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
  });

  const strategy = strategiesData?.strategies.find((s) => s.id === strategyId);

  const evaluateMutation = useMutation({
    mutationFn: () => evaluateStrategy(strategyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      queryClient.invalidateQueries({ queryKey: ['strategies', strategyId, 'signals'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteStrategy(strategyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      onDeleted();
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <div className="h-6 w-1/2 animate-pulse rounded bg-gray-100" />
        <div className="h-20 animate-pulse rounded bg-gray-100" />
      </div>
    );
  }

  if (isError || !strategy) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-gray-400">
        전략을 불러올 수 없습니다.
      </div>
    );
  }

  const indicators = strategy.rule?.indicators ?? [];

  return (
    <article className="rounded-xl border border-gray-200 bg-white shadow-card">
      {/* Header */}
      <header className="flex items-start justify-between gap-4 border-b border-gray-100 px-5 py-4">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-gray-900">{strategy.name}</h2>
          <div className="mt-0.5 text-sm text-gray-500">
            {strategy.symbol} · {strategy.nameKr}
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-medium text-gray-500">
              {strategy.executionMode === 'signal_only' ? '신호전용' : '자동'}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => onEdit(strategy.id)}
            className="rounded-md border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            편집
          </button>
          <button
            type="button"
            onClick={() => {
              if (window.confirm(`"${strategy.name}" 전략을 삭제하시겠습니까?`)) {
                deleteMutation.mutate();
              }
            }}
            disabled={deleteMutation.isPending}
            className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-500 transition-colors hover:bg-red-50 disabled:opacity-50"
          >
            삭제
          </button>
        </div>
      </header>

      <div className="flex flex-col gap-6 p-5">
        {/* Latest signal */}
        <section>
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-gray-500">
            최근 신호
          </h3>
          {strategy.lastSignal ? (
            <LatestSignalCard signal={strategy.lastSignal} />
          ) : (
            <div className="rounded-lg border border-dashed border-gray-200 p-4 text-center text-sm text-gray-400">
              아직 평가 신호가 없습니다.
            </div>
          )}
        </section>

        {/* Evaluate button */}
        <section>
          <button
            type="button"
            onClick={() => evaluateMutation.mutate()}
            disabled={evaluateMutation.isPending}
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {evaluateMutation.isPending ? '평가 중…' : '지금 평가 (드라이런)'}
          </button>
          {evaluateMutation.isError ? (
            <p className="mt-2 text-sm text-red-500">평가에 실패했습니다. 다시 시도하세요.</p>
          ) : null}
          {evaluateMutation.isSuccess ? (
            <div className="mt-3">
              <LatestSignalCard signal={evaluateMutation.data} />
            </div>
          ) : null}
        </section>

        {/* Rule summary */}
        {indicators.length > 0 ? (
          <section>
            <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-gray-500">
              규칙
            </h3>
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <IndicatorSummary indicators={indicators} />
              {indicators.length > 1 ? (
                <p className="mt-2 text-xs text-gray-400">
                  모든 지표가 동의해야 매수/매도 신호가 발생합니다.
                </p>
              ) : null}
            </div>
          </section>
        ) : null}

        {/* Signal history */}
        <section>
          <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-gray-500">
            신호 내역
          </h3>
          <SignalHistory strategyId={strategyId} />
        </section>
      </div>
    </article>
  );
}
