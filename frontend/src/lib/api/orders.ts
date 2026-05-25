// Orders API. Covers placing, listing, cancelling, and modifying orders
// for the Trading page. All mutations go through `apiRequest` so the
// `Content-Type: application/json` header is attached to POST/PATCH/DELETE.

import type {
  Order,
  OrderModifyRequest,
  OrderRequest,
  OrdersResult,
} from '@/types/orders';

import { toOrder } from './adapters';
import { apiRequest } from './client';
import { isMockEnabled, mockApi } from './mock';

// GET /api/v1/orders returns `{orders, count}` per backend ORDERS spec.
interface OrdersEnvelope {
  orders: Parameters<typeof toOrder>[0][];
  count: number;
}

export async function fetchOrders(): Promise<OrdersResult> {
  if (isMockEnabled()) return mockApi.getOrders();
  const raw = await apiRequest<OrdersEnvelope>('/api/v1/orders');
  return {
    orders: raw.orders.map(toOrder),
    count: raw.count,
  };
}

export async function fetchOrder(id: number): Promise<Order> {
  if (isMockEnabled()) return mockApi.getOrder(id);
  const raw = await apiRequest<Parameters<typeof toOrder>[0]>(`/api/v1/orders/${id}`);
  return toOrder(raw);
}

export async function placeOrder(request: OrderRequest): Promise<Order> {
  if (isMockEnabled()) return mockApi.placeOrder(request);
  // Request body uses snake_case keys to match backend ORDERS spec.
  const raw = await apiRequest<Parameters<typeof toOrder>[0]>('/api/v1/orders', {
    method: 'POST',
    body: {
      symbol: request.symbol,
      side: request.side,
      order_type: request.orderType,
      quantity: request.quantity,
      price: request.price,
    },
  });
  return toOrder(raw);
}

export async function cancelOrder(id: number): Promise<void> {
  if (isMockEnabled()) {
    mockApi.cancelOrder(id);
    return;
  }
  await apiRequest<null>(`/api/v1/orders/${id}`, { method: 'DELETE' });
}

export async function modifyOrder(
  id: number,
  patch: OrderModifyRequest,
): Promise<Order> {
  if (isMockEnabled()) return mockApi.modifyOrder(id, patch);
  const raw = await apiRequest<Parameters<typeof toOrder>[0]>(`/api/v1/orders/${id}`, {
    method: 'PATCH',
    body: patch,
  });
  return toOrder(raw);
}
