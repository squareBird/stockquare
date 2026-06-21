// Strategy domain types for the Strategy page.
// Backend responses are snake_case; these camelCase types are what components
// consume after passing through the adapter layer in `lib/api/adapters.ts`.

export type StrategyType = 'rule' | 'ai' | 'hybrid'; // Phase 1 UI: 'rule' only
export type ExecutionMode = 'signal_only' | 'auto'; // Phase 1 UI: 'signal_only'
export type SignalAction = 'buy' | 'sell' | 'hold';
export type IndicatorKind = 'ma_cross' | 'rsi' | 'bollinger';

export interface Indicator {
  kind: IndicatorKind;
  // kind-specific params (fast/slow, period/oversold/overbought, period/mult)
  [param: string]: number | string;
}

export interface Signal {
  action: SignalAction;
  confidence: number; // 0.0–1.0
  rationale: string;
  executed: boolean;
  orderId?: string | null;
  createdAt: string;
}

export type SizingConfig =
  | { mode: 'fixed_quantity'; quantity: number }
  | { mode: 'fixed_amount'; amountKrw: number };

export interface Strategy {
  id: number;
  name: string;
  symbol: string;
  nameKr: string;
  strategyType: StrategyType;
  executionMode: ExecutionMode;
  sidePolicy: string;
  rule: { indicators: Indicator[] } | null;
  sizing: SizingConfig;
  active: boolean;
  createdAt: string;
  lastSignal: Signal | null;
}

export interface StrategiesResult {
  strategies: Strategy[];
  count: number;
}

// Form payload for creating or updating a strategy.
export interface StrategyFormData {
  name: string;
  symbol: string;
  rule: { indicators: Indicator[] };
  sizing: SizingConfig;
}
