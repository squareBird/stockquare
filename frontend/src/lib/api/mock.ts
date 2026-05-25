// Static mock data used in development when the backend is unavailable.
// Activated only when `NEXT_PUBLIC_USE_MOCK === 'true'`. Never used in production.

import type {
  AccountStatus,
  AccountSummary,
  MarketIndex,
  MarketIndicesResult,
  StockSearchResult,
  WatchlistItem,
  WatchlistResult,
} from '@/types/dashboard';
import type {
  Order,
  OrderModifyRequest,
  OrderRequest,
  OrdersResult,
} from '@/types/orders';
import type { Holding, HoldingsResult } from '@/types/portfolio';

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

let mockOrders: Order[] = [];
let nextOrderId = 1;

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
        s.symbol.toLowerCase().includes(normalized) ||
        s.name.toLowerCase().includes(normalized),
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
    mockOrders = [
      ...mockOrders.slice(0, index),
      updated,
      ...mockOrders.slice(index + 1),
    ];
    return updated;
  },
};
