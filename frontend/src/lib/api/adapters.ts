// Adapter layer mapping snake_case backend responses to camelCase domain types.
// Keeping this separate lets components stay in idiomatic camelCase while the
// backend contract owns the wire format.

import type {
  AccountConnectionStatus,
  AccountStatus,
  AccountSummary,
  MarketIndex,
  MarketIndexError,
  MarketStatus,
  StockSearchResult,
  WatchlistItem,
  WatchlistItemError,
} from '@/types/dashboard';

interface AccountStatusResponse {
  status: AccountConnectionStatus;
  account_number?: string;
  message?: string;
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

export function toAccountStatus(raw: AccountStatusResponse): AccountStatus {
  return {
    status: raw.status,
    accountNumber: raw.account_number,
    message: raw.message,
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
