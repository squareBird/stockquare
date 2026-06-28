'use client';

import { useEffect, useMemo, useState } from 'react';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { searchStocks } from '@/lib/api/stocks';
import { createStrategy, fetchStrategies, updateStrategy } from '@/lib/api/strategy';
import type { Indicator, IndicatorKind, SizingConfig } from '@/types/strategy';

interface StrategyFormProps {
  // When editId is set the form operates in edit mode
  editId: number | null;
  onClose: () => void;
}

type SizingMode = 'fixed_quantity' | 'fixed_amount';

interface IndicatorRow {
  kind: IndicatorKind;
  // ma_cross
  fast?: number;
  slow?: number;
  // rsi
  period?: number;
  oversold?: number;
  overbought?: number;
  // bollinger
  mult?: number;
}

function defaultRowForKind(kind: IndicatorKind): IndicatorRow {
  if (kind === 'ma_cross') return { kind, fast: 5, slow: 20 };
  if (kind === 'rsi') return { kind, period: 14, oversold: 30, overbought: 70 };
  return { kind, period: 20, mult: 2 };
}

function rowToIndicator(row: IndicatorRow): Indicator {
  if (row.kind === 'ma_cross') {
    return { kind: 'ma_cross', fast: row.fast ?? 5, slow: row.slow ?? 20 };
  }
  if (row.kind === 'rsi') {
    return {
      kind: 'rsi',
      period: row.period ?? 14,
      oversold: row.oversold ?? 30,
      overbought: row.overbought ?? 70,
    };
  }
  return { kind: 'bollinger', period: row.period ?? 20, mult: row.mult ?? 2 };
}

function buildSizing(mode: SizingMode, quantity: number, amountKrw: number): SizingConfig {
  if (mode === 'fixed_quantity') return { mode: 'fixed_quantity', quantity };
  return { mode: 'fixed_amount', amountKrw };
}

function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

const KIND_LABELS: Record<IndicatorKind, string> = {
  ma_cross: 'MA 골든크로스',
  rsi: 'RSI',
  bollinger: '볼린저밴드',
};

export default function StrategyForm({ editId, onClose }: StrategyFormProps) {
  const queryClient = useQueryClient();

  // Pre-fill form when editing
  const { data: strategiesData } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
    enabled: editId !== null,
  });
  const editTarget = useMemo(
    () => (editId !== null ? (strategiesData?.strategies.find((s) => s.id === editId) ?? null) : null),
    [editId, strategiesData],
  );

  const [name, setName] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState<{ symbol: string; name: string } | null>(null);
  const [symbolQuery, setSymbolQuery] = useState('');
  const debouncedQuery = useDebouncedValue(symbolQuery, 300);
  const [indicators, setIndicators] = useState<IndicatorRow[]>([
    { kind: 'ma_cross', fast: 5, slow: 20 },
  ]);
  const [sizingMode, setSizingMode] = useState<SizingMode>('fixed_amount');
  const [quantity, setQuantity] = useState(1);
  const [amountKrw, setAmountKrw] = useState(50_000);
  const [fieldError, setFieldError] = useState<string | null>(null);

  // Pre-fill the form once the edit target loads. The target arrives
  // asynchronously (from the strategies query), so a remount key can't seed
  // the fields; instead we adjust state during render the first time we see a
  // given target, tracking which one we've already applied.
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  const [prefilledId, setPrefilledId] = useState<number | null>(null);
  if (editTarget && editTarget.id !== prefilledId) {
    setPrefilledId(editTarget.id);
    setName(editTarget.name);
    setSelectedSymbol({ symbol: editTarget.symbol, name: editTarget.nameKr });
    setSymbolQuery(editTarget.symbol);
    if (editTarget.rule?.indicators) {
      setIndicators(editTarget.rule.indicators.map((ind) => ({ ...ind }) as IndicatorRow));
    }
    if (editTarget.sizing.mode === 'fixed_quantity') {
      setSizingMode('fixed_quantity');
      setQuantity(editTarget.sizing.quantity);
    } else {
      setSizingMode('fixed_amount');
      setAmountKrw(editTarget.sizing.amountKrw);
    }
  }

  // Symbol search
  const symbolSearchEnabled = debouncedQuery.trim().length > 0 && !selectedSymbol;
  const { data: searchResults, isFetching: isSearching } = useQuery({
    queryKey: ['stocks', 'search', debouncedQuery],
    queryFn: () => searchStocks(debouncedQuery),
    enabled: symbolSearchEnabled,
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error('전략 이름을 입력하세요.');
      if (!selectedSymbol) throw new Error('종목을 선택하세요.');
      if (indicators.length === 0) throw new Error('지표를 하나 이상 추가하세요.');

      const rule = { indicators: indicators.map(rowToIndicator) as Record<string, number | string>[] };
      const sizing = buildSizing(sizingMode, quantity, amountKrw);

      if (editId !== null) {
        return updateStrategy(editId, { name: name.trim(), rule, sizing });
      }
      return createStrategy({ name: name.trim(), symbol: selectedSymbol.symbol, rule, sizing });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      onClose();
    },
    onError: (error) => {
      setFieldError(error instanceof Error ? error.message : '저장에 실패했습니다.');
    },
  });

  function addIndicator() {
    setIndicators((prev) => [...prev, defaultRowForKind('ma_cross')]);
  }

  function removeIndicator(idx: number) {
    setIndicators((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateIndicatorKind(idx: number, kind: IndicatorKind) {
    setIndicators((prev) =>
      prev.map((row, i) => (i === idx ? defaultRowForKind(kind) : row)),
    );
  }

  function updateIndicatorField(idx: number, field: string, value: number) {
    setIndicators((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, [field]: value } : row)),
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-card">
      <header className="mb-5 flex items-center justify-between">
        <h2 className="text-base font-semibold tracking-tight text-gray-900">
          {editId !== null ? '전략 편집' : '새 전략'}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close form"
        >
          ✕
        </button>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setFieldError(null);
          saveMutation.mutate();
        }}
        className="flex flex-col gap-4"
      >
        {/* Name */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-gray-600" htmlFor="strategy-name">
            전략 이름 <span className="text-red-500">*</span>
          </label>
          <input
            id="strategy-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={100}
            placeholder="예: 삼성전자 골든크로스"
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
            required
          />
        </div>

        {/* Symbol */}
        <div>
          <label className="mb-1 block text-xs font-semibold text-gray-600" htmlFor="strategy-symbol">
            종목 <span className="text-red-500">*</span>
          </label>
          {selectedSymbol ? (
            <div className="flex items-center justify-between rounded-lg border border-brand-200 bg-brand-50 p-3">
              <div>
                <div className="text-sm font-semibold text-gray-900">{selectedSymbol.name}</div>
                <div className="font-mono text-xs text-gray-500">{selectedSymbol.symbol}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedSymbol(null);
                  setSymbolQuery('');
                }}
                className="text-xs text-brand-600 hover:underline"
              >
                변경
              </button>
            </div>
          ) : (
            <div>
              <input
                id="strategy-symbol"
                type="text"
                value={symbolQuery}
                onChange={(e) => setSymbolQuery(e.target.value)}
                placeholder="종목 검색 (심볼 또는 이름)"
                className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
              />
              {isSearching ? (
                <p className="mt-1 text-xs text-gray-400">검색 중…</p>
              ) : null}
              {!isSearching && searchResults && searchResults.length === 0 && debouncedQuery ? (
                <p className="mt-1 text-xs text-gray-400">검색 결과가 없습니다.</p>
              ) : null}
              {searchResults && searchResults.length > 0 ? (
                <ul className="mt-1 max-h-48 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-sm">
                  {searchResults.map((stock) => (
                    <li key={stock.symbol}>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedSymbol({ symbol: stock.symbol, name: stock.name });
                          setSymbolQuery('');
                        }}
                        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-gray-50"
                      >
                        <span className="text-sm font-medium text-gray-900">{stock.name}</span>
                        <span className="font-mono text-xs text-gray-400">{stock.symbol}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </div>

        {/* Strategy type — fixed to 'rule' in Phase 1, read-only display */}
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-600">전략 유형</div>
          <div className="flex gap-3">
            <span className="rounded-md border border-brand-200 bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700">
              규칙 기반
            </span>
            <span className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-400" title="Phase 2 준비 중">
              AI / 하이브리드 — Phase 2 준비 중
            </span>
          </div>
        </div>

        {/* Execution mode — 'auto' disabled in Phase 1 */}
        <div>
          <div className="mb-1 text-xs font-semibold text-gray-600">실행 모드</div>
          <div className="flex gap-3">
            <span className="rounded-md border border-brand-200 bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700">
              신호전용
            </span>
            <span
              className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-400"
              title="Phase 2 준비 중"
            >
              자동 — Phase 2 준비 중
            </span>
          </div>
        </div>

        {/* Active toggle — disabled in Phase 1 */}
        <div className="flex items-center gap-3">
          <div className="text-xs font-semibold text-gray-400">전략 활성화</div>
          <div className="flex items-center gap-2 opacity-50">
            <div
              className="h-5 w-9 cursor-not-allowed rounded-full bg-gray-300"
              title="Phase 2 준비 중"
              aria-disabled="true"
            />
            <span className="text-xs text-gray-400">Phase 2 준비 중</span>
          </div>
        </div>

        {/* Indicator builder */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <div className="text-xs font-semibold text-gray-600">지표 <span className="text-red-500">*</span></div>
            <button
              type="button"
              onClick={addIndicator}
              className="rounded px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50"
            >
              + 지표 추가
            </button>
          </div>
          {indicators.length > 1 ? (
            <p className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
              모든 지표가 동의해야 매수/매도 신호가 발생합니다.
            </p>
          ) : null}
          <div className="space-y-3">
            {indicators.map((row, idx) => (
              // Indicator index is stable within the form lifecycle; idx is safe here
               
              <div key={idx} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <select
                    value={row.kind}
                    onChange={(e) => updateIndicatorKind(idx, e.target.value as IndicatorKind)}
                    className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 focus:border-brand-600 focus:outline-none"
                    aria-label={`Indicator ${idx + 1} kind`}
                  >
                    {(Object.keys(KIND_LABELS) as IndicatorKind[]).map((k) => (
                      <option key={k} value={k}>
                        {KIND_LABELS[k]}
                      </option>
                    ))}
                  </select>
                  {indicators.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => removeIndicator(idx)}
                      className="rounded px-1.5 py-0.5 text-xs text-gray-400 hover:bg-gray-200 hover:text-red-500"
                      aria-label={`Remove indicator ${idx + 1}`}
                    >
                      삭제
                    </button>
                  ) : null}
                </div>

                {row.kind === 'ma_cross' ? (
                  <div className="flex gap-3">
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      빠른 MA
                      <input
                        type="number"
                        min={1}
                        max={200}
                        value={row.fast ?? 5}
                        onChange={(e) => updateIndicatorField(idx, 'fast', parseInt(e.target.value, 10))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="Fast MA period"
                      />
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      느린 MA
                      <input
                        type="number"
                        min={1}
                        max={200}
                        value={row.slow ?? 20}
                        onChange={(e) => updateIndicatorField(idx, 'slow', parseInt(e.target.value, 10))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="Slow MA period"
                      />
                    </label>
                  </div>
                ) : null}

                {row.kind === 'rsi' ? (
                  <div className="flex flex-wrap gap-3">
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      기간
                      <input
                        type="number"
                        min={2}
                        max={100}
                        value={row.period ?? 14}
                        onChange={(e) => updateIndicatorField(idx, 'period', parseInt(e.target.value, 10))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="RSI period"
                      />
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      과매도
                      <input
                        type="number"
                        min={1}
                        max={49}
                        value={row.oversold ?? 30}
                        onChange={(e) => updateIndicatorField(idx, 'oversold', parseInt(e.target.value, 10))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="RSI oversold threshold"
                      />
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      과매수
                      <input
                        type="number"
                        min={51}
                        max={99}
                        value={row.overbought ?? 70}
                        onChange={(e) => updateIndicatorField(idx, 'overbought', parseInt(e.target.value, 10))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="RSI overbought threshold"
                      />
                    </label>
                  </div>
                ) : null}

                {row.kind === 'bollinger' ? (
                  <div className="flex gap-3">
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      기간
                      <input
                        type="number"
                        min={2}
                        max={200}
                        value={row.period ?? 20}
                        onChange={(e) => updateIndicatorField(idx, 'period', parseInt(e.target.value, 10))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="Bollinger period"
                      />
                    </label>
                    <label className="flex items-center gap-1.5 text-xs text-gray-600">
                      배수
                      <input
                        type="number"
                        min={0.5}
                        max={5}
                        step={0.1}
                        value={row.mult ?? 2}
                        onChange={(e) => updateIndicatorField(idx, 'mult', parseFloat(e.target.value))}
                        className="w-16 rounded border border-gray-300 px-2 py-1 text-sm focus:border-brand-600 focus:outline-none"
                        aria-label="Bollinger band multiplier"
                      />
                    </label>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>

        {/* Sizing */}
        <div>
          <div className="mb-2 text-xs font-semibold text-gray-600">주문 규모</div>
          <div className="mb-3 flex gap-2">
            <button
              type="button"
              onClick={() => setSizingMode('fixed_amount')}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
                sizingMode === 'fixed_amount'
                  ? 'border-brand-200 bg-brand-50 text-brand-700'
                  : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              금액 고정
            </button>
            <button
              type="button"
              onClick={() => setSizingMode('fixed_quantity')}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-colors ${
                sizingMode === 'fixed_quantity'
                  ? 'border-brand-200 bg-brand-50 text-brand-700'
                  : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}
            >
              수량 고정
            </button>
          </div>
          {sizingMode === 'fixed_amount' ? (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              금액 (원)
              <input
                type="number"
                min={1000}
                step={1000}
                value={amountKrw}
                onChange={(e) => setAmountKrw(parseInt(e.target.value, 10))}
                className="w-32 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-brand-600 focus:outline-none"
                aria-label="Order amount in KRW"
              />
            </label>
          ) : (
            <label className="flex items-center gap-2 text-sm text-gray-700">
              수량 (주)
              <input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(parseInt(e.target.value, 10))}
                className="w-32 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-brand-600 focus:outline-none"
                aria-label="Order quantity in shares"
              />
            </label>
          )}
        </div>

        {fieldError ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{fieldError}</p>
        ) : null}

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            disabled={saveMutation.isPending}
            className="flex-1 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {saveMutation.isPending ? '저장 중…' : editId !== null ? '수정 저장' : '전략 생성'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            취소
          </button>
        </div>
      </form>
    </div>
  );
}
