// Order domain types for the Trading page.

export type OrderSide = 'buy' | 'sell';

export type OrderType = 'limit' | 'market';

export type OrderStatus =
  | 'pending'
  | 'accepted'
  | 'partially_filled'
  | 'filled'
  | 'cancelled'
  | 'rejected';

export interface Order {
  id: number;
  symbol: string;
  name: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  price: number; // 0 for market orders
  filledQuantity: number;
  filledPrice: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
}

export interface OrderRequest {
  symbol: string;
  side: OrderSide;
  orderType: OrderType;
  quantity: number;
  price: number; // 0 for market orders
}

export interface OrderModifyRequest {
  quantity?: number;
  price?: number;
}

export interface OrdersResult {
  orders: Order[];
  count: number;
}
