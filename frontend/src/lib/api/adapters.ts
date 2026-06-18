// Adapter layer mapping snake_case backend responses to camelCase domain types.
// Keeping this separate lets components stay in idiomatic camelCase while the
// backend contract owns the wire format.

import type { Candle, ChartPeriod, StockHistoryResult } from '@/types/charts';
import type {
  AccountConnectionStatus,
  AccountMode,
  AccountStatus,
  AccountSummary,
  MarketIndex,
  MarketIndexError,
  MarketStatus,
  StockSearchResult,
  WatchlistItem,
  WatchlistItemError,
} from '@/types/dashboard';
import type { Order, OrderSide, OrderStatus, OrderType } from '@/types/orders';
import type { Holding, HoldingError } from '@/types/portfolio';

interface AccountStatusResponse {
  status: AccountConnectionStatus;
  account_number?: string;
  account_mode?: AccountMode;
  message?: string;
}

interface HoldingResponse {
  symbol: string;
  name: string;
  quantity: number;
  avg_purchase_price: number;
  current_price: number;
  evaluation_amount: number;
  purchase_amount: number;
  profit: number;
  profit_rate: number;
}

interface HoldingErrorResponse {
  symbol: string;
  name: string;
  quantity: number;
  avg_purchase_price: number;
  purchase_amount: number;
  error_code: string;
  message: string;
}

interface OrderResponse {
  id: number;
  symbol: string;
  name: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  price: number;
  filled_quantity: number;
  filled_price: number;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

interface AccountSummaryResponse {
  total_asset: number;
  daily_profit: number;
  daily_profit_rate: number;
  cash_balance: number;
}

interface WatchlistItemResponse {
  id: number;
  sort_order: number;
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_rate: number;
  volume: number;
}

interface WatchlistItemErrorResponse {
  id: number;
  symbol: string;
  error_code: string;
  message: string;
}

interface MarketIndexResponse {
  code: string;
  name: string;
  value: number;
  change: number;
  change_rate: number;
  volume: number;
  status: MarketStatus;
}

interface MarketIndexErrorResponse {
  code: string;
  name: string;
  error_code: string;
  message: string;
}

interface StockSearchResultResponse {
  symbol: string;
  name: string;
  market: string;
}

interface CandleResponse {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface StockHistoryResponse {
  symbol: string;
  period: ChartPeriod;
  candles: CandleResponse[];
}

export function toAccountStatus(raw: AccountStatusResponse): AccountStatus {
  return {
    status: raw.status,
    accountNumber: raw.account_number,
    accountMode: raw.account_mode,
    message: raw.message,
  };
}

export function toHolding(raw: HoldingResponse): Holding {
  return {
    symbol: raw.symbol,
    name: raw.name,
    quantity: raw.quantity,
    avgPurchasePrice: raw.avg_purchase_price,
    currentPrice: raw.current_price,
    evaluationAmount: raw.evaluation_amount,
    purchaseAmount: raw.purchase_amount,
    profit: raw.profit,
    profitRate: raw.profit_rate,
  };
}

export function toHoldingError(raw: HoldingErrorResponse): HoldingError {
  return {
    symbol: raw.symbol,
    name: raw.name,
    quantity: raw.quantity,
    avgPurchasePrice: raw.avg_purchase_price,
    purchaseAmount: raw.purchase_amount,
    errorCode: raw.error_code,
    message: raw.message,
  };
}

export function toOrder(raw: OrderResponse): Order {
  return {
    id: raw.id,
    symbol: raw.symbol,
    name: raw.name,
    side: raw.side,
    orderType: raw.order_type,
    quantity: raw.quantity,
    price: raw.price,
    filledQuantity: raw.filled_quantity,
    filledPrice: raw.filled_price,
    status: raw.status,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export function toAccountSummary(raw: AccountSummaryResponse): AccountSummary {
  return {
    totalAsset: raw.total_asset,
    dailyProfit: raw.daily_profit,
    dailyProfitRate: raw.daily_profit_rate,
    cashBalance: raw.cash_balance,
  };
}

export function toWatchlistItem(raw: WatchlistItemResponse): WatchlistItem {
  return {
    id: raw.id,
    sortOrder: raw.sort_order,
    symbol: raw.symbol,
    name: raw.name,
    price: raw.price,
    change: raw.change,
    changeRate: raw.change_rate,
    volume: raw.volume,
  };
}

export function toMarketIndex(raw: MarketIndexResponse): MarketIndex {
  return {
    code: raw.code,
    name: raw.name,
    value: raw.value,
    change: raw.change,
    changeRate: raw.change_rate,
    volume: raw.volume,
    status: raw.status,
  };
}

export function toMarketIndexError(raw: MarketIndexErrorResponse): MarketIndexError {
  return {
    code: raw.code,
    name: raw.name,
    errorCode: raw.error_code,
    message: raw.message,
  };
}

export function toWatchlistItemError(raw: WatchlistItemErrorResponse): WatchlistItemError {
  return {
    id: raw.id,
    symbol: raw.symbol,
    errorCode: raw.error_code,
    message: raw.message,
  };
}

export function toStockSearchResult(raw: StockSearchResultResponse): StockSearchResult {
  return {
    symbol: raw.symbol,
    name: raw.name,
    market: raw.market,
  };
}

export function toCandle(raw: CandleResponse): Candle {
  return {
    time: raw.time,
    open: raw.open,
    high: raw.high,
    low: raw.low,
    close: raw.close,
    volume: raw.volume,
  };
}

export function toStockHistory(raw: StockHistoryResponse): StockHistoryResult {
  return {
    symbol: raw.symbol,
    period: raw.period,
    candles: raw.candles.map(toCandle),
  };
}
