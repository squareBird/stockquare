// Static mock data used in development when the backend is unavailable.
// Activated only when `NEXT_PUBLIC_USE_MOCK === 'true'`. Never used in production.

import type { Candle, ChartPeriod, StockHistoryResult } from '@/types/charts';
import type {
  AccountStatus,
  AccountSummary,
  MarketIndex,
  MarketIndicesResult,
  StockSearchResult,
  WatchlistItem,
  WatchlistResult,
} from '@/types/dashboard';
import type { Order, OrderModifyRequest, OrderRequest, OrdersResult } from '@/types/orders';
import type { Holding, HoldingsResult } from '@/types/portfolio';
import type { Signal, Strategy, StrategiesResult } from '@/types/strategy';

export const isMockEnabled = (): boolean =>
  process.env.NODE_ENV !== 'production' && process.env.NEXT_PUBLIC_USE_MOCK === 'true';

const MOCK_ACCOUNT_STATUS: AccountStatus = {
  status: 'connected',
  accountNumber: '****1234',
  accountMode: 'mock',
};

const MOCK_ACCOUNT_SUMMARY: AccountSummary = {
  totalAsset: 12_345_678,
  dailyProfit: 123_456,
  dailyProfitRate: 1.23,
  cashBalance: 5_000_000,
};

const MOCK_WATCHLIST: WatchlistItem[] = [
  {
    id: 1,
    sortOrder: 0,
    symbol: '005930',
    name: 'Samsung Electronics',
    price: 72_300,
    change: 1_200,
    changeRate: 1.69,
    volume: 12_345_678,
  },
  {
    id: 2,
    sortOrder: 1,
    symbol: '000660',
    name: 'SK Hynix',
    price: 198_500,
    change: -3_500,
    changeRate: -1.73,
    volume: 5_432_109,
  },
  {
    id: 3,
    sortOrder: 2,
    symbol: '035420',
    name: 'NAVER',
    price: 187_000,
    change: 0,
    changeRate: 0,
    volume: 987_654,
  },
];

const MOCK_MARKET_INDICES: MarketIndex[] = [
  {
    code: 'KOSPI',
    name: 'KOSPI',
    value: 2_687.45,
    change: 15.32,
    changeRate: 0.57,
    volume: 412_567_890,
    status: 'open',
  },
  {
    code: 'KOSDAQ',
    name: 'KOSDAQ',
    value: 871.23,
    change: -2.71,
    changeRate: -0.31,
    volume: 789_012_345,
    status: 'open',
  },
];

const MOCK_SEARCH_UNIVERSE: StockSearchResult[] = [
  { symbol: '005930', name: 'Samsung Electronics', market: 'KOSPI' },
  { symbol: '000660', name: 'SK Hynix', market: 'KOSPI' },
  { symbol: '035420', name: 'NAVER', market: 'KOSPI' },
  { symbol: '035720', name: 'Kakao', market: 'KOSPI' },
  { symbol: '068270', name: 'Celltrion', market: 'KOSPI' },
  { symbol: '247540', name: 'EcoPro BM', market: 'KOSDAQ' },
];

const MOCK_HOLDINGS: Holding[] = [
  {
    symbol: '005930',
    name: 'Samsung Electronics',
    quantity: 10,
    avgPurchasePrice: 71_000,
    currentPrice: 72_300,
    evaluationAmount: 723_000,
    purchaseAmount: 710_000,
    profit: 13_000,
    profitRate: 1.83,
  },
  {
    symbol: '000660',
    name: 'SK Hynix',
    quantity: 5,
    avgPurchasePrice: 205_000,
    currentPrice: 198_500,
    evaluationAmount: 992_500,
    purchaseAmount: 1_025_000,
    profit: -32_500,
    profitRate: -3.17,
  },
];

let mockWatchlist: WatchlistItem[] = [...MOCK_WATCHLIST];
let nextWatchlistId = mockWatchlist.length + 1;

// ---------------------------------------------------------------------------
// Strategy mock data
// ---------------------------------------------------------------------------

const MOCK_SIGNAL_HOLD: Signal = {
  action: 'hold',
  confidence: 0,
  rationale: '충분한 신호가 없습니다. 지표들 사이에 합의가 이루어지지 않았습니다.',
  executed: false,
  orderId: null,
  createdAt: new Date(Date.now() - 5 * 60_000).toISOString(),
};

const MOCK_SIGNAL_BUY: Signal = {
  action: 'buy',
  confidence: 0.78,
  rationale: 'MA(5)가 MA(20)를 상향 돌파했습니다 (골든크로스). RSI 38로 과매도 직전입니다.',
  executed: false,
  orderId: null,
  createdAt: new Date(Date.now() - 2 * 60 * 60_000).toISOString(),
};

const INITIAL_MOCK_STRATEGIES: Strategy[] = [
  {
    id: 1,
    name: '삼성전자 골든크로스',
    symbol: '005930',
    nameKr: 'Samsung Electronics',
    strategyType: 'rule',
    executionMode: 'signal_only',
    sidePolicy: 'long_only',
    rule: {
      indicators: [
        { kind: 'ma_cross', fast: 5, slow: 20 },
        { kind: 'rsi', period: 14, oversold: 30, overbought: 70 },
      ],
    },
    sizing: { mode: 'fixed_amount', amountKrw: 50_000 },
    active: false,
    createdAt: new Date(Date.now() - 7 * 24 * 60 * 60_000).toISOString(),
    lastSignal: MOCK_SIGNAL_HOLD,
  },
  {
    id: 2,
    name: 'SK하이닉스 볼린저밴드',
    symbol: '000660',
    nameKr: 'SK Hynix',
    strategyType: 'rule',
    executionMode: 'signal_only',
    sidePolicy: 'long_only',
    rule: {
      indicators: [{ kind: 'bollinger', period: 20, mult: 2 }],
    },
    sizing: { mode: 'fixed_quantity', quantity: 1 },
    active: false,
    createdAt: new Date(Date.now() - 3 * 24 * 60 * 60_000).toISOString(),
    lastSignal: MOCK_SIGNAL_BUY,
  },
];

const INITIAL_MOCK_SIGNALS: Map<number, Signal[]> = new Map([
  [
    1,
    [
      MOCK_SIGNAL_HOLD,
      {
        action: 'buy',
        confidence: 0.65,
        rationale: 'RSI 28로 과매도 구간입니다.',
        executed: false,
        orderId: null,
        createdAt: new Date(Date.now() - 24 * 60 * 60_000).toISOString(),
      },
    ],
  ],
  [2, [MOCK_SIGNAL_BUY]],
]);

let mockStrategies: Strategy[] = [...INITIAL_MOCK_STRATEGIES];
let mockSignalsByStrategy: Map<number, Signal[]> = new Map(INITIAL_MOCK_SIGNALS);
let nextStrategyId = INITIAL_MOCK_STRATEGIES.length + 1;

let mockOrders: Order[] = [];
let nextOrderId = 1;

const CANDLE_COUNT_BY_PERIOD: Record<ChartPeriod, number> = {
  '1w': 5,
  '1m': 22,
  '3m': 66,
  '1y': 250,
};

// Deterministic-ish synthetic daily candles so the chart renders in mock mode.
// A sine drift plus a seeded pseudo-random wobble keeps the series stable
// enough to read while still looking like price action.
function generateMockCandles(period: ChartPeriod): Candle[] {
  const count = CANDLE_COUNT_BY_PERIOD[period];
  const candles: Candle[] = [];
  const today = new Date();
  let price = 70_000;
  let seed = 1;
  const wobble = (): number => {
    seed = (seed * 1103515245 + 12345) % 2_147_483_648;
    return seed / 2_147_483_648 - 0.5;
  };
  for (let i = count - 1; i >= 0; i -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);
    const open = price;
    const drift = (Math.sin(i / 4) + wobble()) * 900;
    const close = Math.max(1_000, Math.round(open + drift));
    const high = Math.max(open, close) + Math.round(Math.abs(wobble()) * 600);
    const low = Math.min(open, close) - Math.round(Math.abs(wobble()) * 600);
    const volume = 5_000_000 + Math.round(Math.abs(wobble()) * 10_000_000);
    candles.push({ time: date.toISOString().slice(0, 10), open, high, low, close, volume });
    price = close;
  }
  return candles;
}

export const mockApi = {
  getAccountStatus: (): AccountStatus => MOCK_ACCOUNT_STATUS,
  getAccountSummary: (): AccountSummary => MOCK_ACCOUNT_SUMMARY,
  getWatchlist: (): WatchlistResult => ({
    items: [...mockWatchlist].sort((a, b) => a.sortOrder - b.sortOrder),
    errors: [],
  }),
  addWatchlistItem: (symbol: string): WatchlistItem => {
    const base = MOCK_SEARCH_UNIVERSE.find((s) => s.symbol === symbol);
    const item: WatchlistItem = {
      id: nextWatchlistId,
      sortOrder: mockWatchlist.length,
      symbol,
      name: base?.name ?? symbol,
      price: 10_000,
      change: 0,
      changeRate: 0,
      volume: 0,
    };
    nextWatchlistId += 1;
    mockWatchlist = [...mockWatchlist, item];
    return item;
  },
  removeWatchlistItem: (id: number): void => {
    mockWatchlist = mockWatchlist.filter((item) => item.id !== id);
  },
  reorderWatchlist: (ids: number[]): void => {
    const byId = new Map(mockWatchlist.map((item) => [item.id, item]));
    mockWatchlist = ids
      .map((id, index) => {
        const found = byId.get(id);
        return found ? { ...found, sortOrder: index } : null;
      })
      .filter((item): item is WatchlistItem => item !== null);
  },
  getMarketIndices: (): MarketIndicesResult => ({
    indices: MOCK_MARKET_INDICES,
    errors: [],
  }),
  searchStocks: (query: string): StockSearchResult[] => {
    const normalized = query.trim().toLowerCase();
    if (normalized.length === 0) return [];
    return MOCK_SEARCH_UNIVERSE.filter(
      (s) =>
        s.symbol.toLowerCase().includes(normalized) || s.name.toLowerCase().includes(normalized),
    );
  },
  getHoldings: (): HoldingsResult => ({
    holdings: [...MOCK_HOLDINGS],
    errors: [],
  }),
  getOrders: (): OrdersResult => ({
    orders: [...mockOrders].reverse(),
    count: mockOrders.length,
  }),
  getOrder: (id: number): Order => {
    const order = mockOrders.find((o) => o.id === id);
    if (!order) throw new Error(`Mock order ${id} not found`);
    return order;
  },
  placeOrder: (request: OrderRequest): Order => {
    const stock = MOCK_SEARCH_UNIVERSE.find((s) => s.symbol === request.symbol);
    const now = new Date().toISOString();
    const order: Order = {
      id: nextOrderId,
      symbol: request.symbol,
      name: stock?.name ?? request.symbol,
      side: request.side,
      orderType: request.orderType,
      quantity: request.quantity,
      price: request.price,
      filledQuantity: 0,
      filledPrice: 0,
      status: 'pending',
      createdAt: now,
      updatedAt: now,
    };
    nextOrderId += 1;
    mockOrders = [...mockOrders, order];
    return order;
  },
  cancelOrder: (id: number): void => {
    mockOrders = mockOrders.map((order) =>
      order.id === id
        ? { ...order, status: 'cancelled', updatedAt: new Date().toISOString() }
        : order,
    );
  },
  modifyOrder: (id: number, patch: OrderModifyRequest): Order => {
    const index = mockOrders.findIndex((o) => o.id === id);
    if (index === -1) throw new Error(`Mock order ${id} not found`);
    const existing = mockOrders[index];
    if (!existing) throw new Error(`Mock order ${id} not found`);
    const updated: Order = {
      ...existing,
      quantity: patch.quantity ?? existing.quantity,
      price: patch.price ?? existing.price,
      updatedAt: new Date().toISOString(),
    };
    mockOrders = [...mockOrders.slice(0, index), updated, ...mockOrders.slice(index + 1)];
    return updated;
  },
  getStockHistory: (symbol: string, period: ChartPeriod): StockHistoryResult => ({
    symbol,
    period,
    candles: generateMockCandles(period),
  }),

  // Strategy mock API
  getStrategies: (): StrategiesResult => ({
    strategies: [...mockStrategies],
    count: mockStrategies.length,
  }),
  createStrategy: (data: {
    name: string;
    symbol: string;
    rule: Strategy['rule'];
    sizing: Strategy['sizing'];
  }): Strategy => {
    const stock = MOCK_SEARCH_UNIVERSE.find((s) => s.symbol === data.symbol);
    const now = new Date().toISOString();
    const strategy: Strategy = {
      id: nextStrategyId,
      name: data.name,
      symbol: data.symbol,
      nameKr: stock?.name ?? data.symbol,
      strategyType: 'rule',
      executionMode: 'signal_only',
      sidePolicy: 'long_only',
      rule: data.rule,
      sizing: data.sizing,
      active: false,
      createdAt: now,
      lastSignal: null,
    };
    nextStrategyId += 1;
    mockStrategies = [...mockStrategies, strategy];
    return strategy;
  },
  updateStrategy: (id: number, patch: Partial<Strategy>): Strategy => {
    const index = mockStrategies.findIndex((s) => s.id === id);
    if (index === -1) throw new Error(`Mock strategy ${id} not found`);
    const existing = mockStrategies[index];
    if (!existing) throw new Error(`Mock strategy ${id} not found`);
    const updated: Strategy = { ...existing, ...patch };
    mockStrategies = [
      ...mockStrategies.slice(0, index),
      updated,
      ...mockStrategies.slice(index + 1),
    ];
    return updated;
  },
  deleteStrategy: (id: number): void => {
    mockStrategies = mockStrategies.filter((s) => s.id !== id);
    mockSignalsByStrategy.delete(id);
  },
  evaluateStrategy: (id: number): Signal => {
    const strategy = mockStrategies.find((s) => s.id === id);
    if (!strategy) throw new Error(`Mock strategy ${id} not found`);
    const actions = ['buy', 'sell', 'hold'] as const;
    const action = actions[id % 3] ?? 'hold';
    const confidence = action === 'hold' ? 0 : 0.72;
    const rationaleMap: Record<string, string> = {
      buy: 'MA(5)가 MA(20)를 상향 돌파했습니다 (골든크로스). RSI 42로 중립 구간입니다.',
      sell: 'MA(5)가 MA(20)를 하향 돌파했습니다 (데드크로스). RSI 68로 과매수 구간에 근접합니다.',
      hold: '충분한 신호가 없습니다. 지표들 사이에 합의가 이루어지지 않았습니다.',
    };
    const signal: Signal = {
      action,
      confidence,
      rationale: rationaleMap[action] ?? '',
      executed: false,
      orderId: null,
      createdAt: new Date().toISOString(),
    };
    // Persist in history and update lastSignal on the strategy
    const existing = mockSignalsByStrategy.get(id) ?? [];
    mockSignalsByStrategy.set(id, [signal, ...existing]);
    const strategyIndex = mockStrategies.findIndex((s) => s.id === id);
    if (strategyIndex !== -1) {
      const s = mockStrategies[strategyIndex];
      if (s) {
        mockStrategies = [
          ...mockStrategies.slice(0, strategyIndex),
          { ...s, lastSignal: signal },
          ...mockStrategies.slice(strategyIndex + 1),
        ];
      }
    }
    return signal;
  },
  getSignals: (id: number): Signal[] => {
    return mockSignalsByStrategy.get(id) ?? [];
  },
};
