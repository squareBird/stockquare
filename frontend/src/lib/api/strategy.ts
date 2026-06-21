// Strategy API calls. Covers listing, creating, updating, deleting strategies
// and evaluating them (dry-run only in Phase 1).
//
// Backend contract: `.aicontext/spec/backend/STRATEGY.md`.

import type { Signal, SizingConfig, Strategy, StrategiesResult } from '@/types/strategy';

import { toSignal, toStrategy } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

// ---------------------------------------------------------------------------
// Response envelope types (snake_case wire format)
// ---------------------------------------------------------------------------

interface StrategyRaw {
  id: number;
  name: string;
  symbol: string;
  name_kr: string;
  strategy_type: string;
  execution_mode: string;
  side_policy: string;
  rule: { indicators: Record<string, number | string>[] } | null;
  sizing: { mode: string; quantity?: number; amount_krw?: number };
  active: boolean;
  created_at: string;
  last_signal: SignalRaw | null;
}

interface SignalRaw {
  action: string;
  confidence: number;
  rationale: string;
  executed: boolean;
  order_id?: string | null;
  created_at: string;
}

interface StrategiesEnvelope {
  strategies: StrategyRaw[];
  count: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function fetchStrategies(): Promise<StrategiesResult> {
  if (isMockEnabled()) return mockApi.getStrategies();
  const raw = await apiRequest<StrategiesEnvelope>('/api/v1/strategies');
  return {
    strategies: raw.strategies.map((s) => toStrategy(s as Parameters<typeof toStrategy>[0])),
    count: raw.count,
  };
}

interface CreateStrategyPayload {
  name: string;
  symbol: string;
  rule: { indicators: Record<string, number | string>[] };
  sizing: SizingConfig;
}

// Converts camelCase sizing to snake_case for the backend.
function sizingToWire(sizing: SizingConfig): Record<string, unknown> {
  if (sizing.mode === 'fixed_quantity') {
    return { mode: 'fixed_quantity', quantity: sizing.quantity };
  }
  return { mode: 'fixed_amount', amount_krw: sizing.amountKrw };
}

export async function createStrategy(payload: CreateStrategyPayload): Promise<Strategy> {
  if (isMockEnabled()) {
    return mockApi.createStrategy({
      name: payload.name,
      symbol: payload.symbol,
      rule: payload.rule as Strategy['rule'],
      sizing: payload.sizing,
    });
  }
  const raw = await apiRequest<StrategyRaw>('/api/v1/strategies', {
    method: 'POST',
    body: {
      name: payload.name,
      symbol: payload.symbol,
      strategy_type: 'rule',
      execution_mode: 'signal_only',
      side_policy: 'long_only',
      rule: payload.rule,
      sizing: sizingToWire(payload.sizing),
      active: false,
    },
  });
  return toStrategy(raw as Parameters<typeof toStrategy>[0]);
}

export async function updateStrategy(
  id: number,
  payload: Partial<CreateStrategyPayload>,
): Promise<Strategy> {
  if (isMockEnabled()) {
    return mockApi.updateStrategy(id, {
      ...(payload.name !== undefined && { name: payload.name }),
      ...(payload.rule !== undefined && { rule: payload.rule as Strategy['rule'] }),
      ...(payload.sizing !== undefined && { sizing: payload.sizing }),
    });
  }
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.rule !== undefined) body.rule = payload.rule;
  if (payload.sizing !== undefined) body.sizing = sizingToWire(payload.sizing);
  const raw = await apiRequest<StrategyRaw>(`/api/v1/strategies/${id}`, {
    method: 'PATCH',
    body,
  });
  return toStrategy(raw as Parameters<typeof toStrategy>[0]);
}

export async function deleteStrategy(id: number): Promise<void> {
  if (isMockEnabled()) {
    mockApi.deleteStrategy(id);
    return;
  }
  await apiRequest<null>(`/api/v1/strategies/${id}`, { method: 'DELETE' });
}

// POST /api/v1/strategies/{id}/evaluate — always a dry-run, never places an order.
export async function evaluateStrategy(id: number): Promise<Signal> {
  if (isMockEnabled()) return mockApi.evaluateStrategy(id);
  const raw = await apiRequest<SignalRaw>(`/api/v1/strategies/${id}/evaluate`, {
    method: 'POST',
  });
  return toSignal(raw as Parameters<typeof toSignal>[0]);
}

interface SignalsEnvelope {
  signals: SignalRaw[];
  count: number;
}

export async function fetchSignals(id: number): Promise<Signal[]> {
  if (isMockEnabled()) return mockApi.getSignals(id);
  const raw = await apiRequest<SignalsEnvelope>(`/api/v1/strategies/${id}/signals`);
  return raw.signals.map((s) => toSignal(s as Parameters<typeof toSignal>[0]));
}
