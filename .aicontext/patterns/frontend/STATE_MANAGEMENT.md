# State Management Pattern

Zustand for client state + TanStack Query for server state.

## Server State — TanStack Query

All data fetched from APIs is managed via TanStack Query.

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Query
export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: () => fetchPortfolio(),
    refetchInterval: 30_000,
  });
}

// Mutation with cache invalidation
export function usePlaceOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (order: OrderRequest) => placeOrder(order),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });
}
```

### Query Key Convention

```typescript
['portfolio']                     // Full portfolio
['stock', symbol]                 // Stock info by symbol
['stock', symbol, 'price']        // Stock price by symbol
['orders']                        // All orders
['orders', { status: 'pending' }] // Filtered orders
```

## Client State — Zustand

UI state and user preferences that are independent of the server.

```typescript
import { create } from 'zustand';

interface TradingUIState {
  selectedSymbol: string | null;
  isSidebarOpen: boolean;
  setSelectedSymbol: (symbol: string) => void;
  toggleSidebar: () => void;
}

export const useTradingUI = create<TradingUIState>((set) => ({
  selectedSymbol: null,
  isSidebarOpen: true,
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
}));
```

## Where Each State Lives

| State | Tool | Example |
|-------|------|---------|
| Server data | TanStack Query | Portfolio, stock price, order history |
| UI state | Zustand | Selected symbol, sidebar toggle, modal |
| Form input | React state | Order quantity, price input |
| URL state | Next.js router | Current page, search params |
