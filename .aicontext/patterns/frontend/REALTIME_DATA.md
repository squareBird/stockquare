# Realtime Data Pattern

Frontend patterns for receiving real-time data via WebSocket.

## WebSocket Connection Manager

Maintain a single WebSocket connection with auto-reconnect.

```typescript
class StockWebSocket {
  private ws: WebSocket | null = null;
  private subscriptions = new Set<string>();
  private listeners = new Map<string, Set<(data: StockTick) => void>>();
  private reconnectDelay = 3000;

  connect(url: string): void {
    this.ws = new WebSocket(url);

    this.ws.onmessage = (event) => {
      const tick: StockTick = JSON.parse(event.data);
      this.listeners.get(tick.symbol)?.forEach((cb) => cb(tick));
    };

    this.ws.onclose = () => {
      setTimeout(() => this.connect(url), this.reconnectDelay);
    };
  }

  subscribe(symbol: string, callback: (data: StockTick) => void): () => void {
    this.subscriptions.add(symbol);
    if (!this.listeners.has(symbol)) {
      this.listeners.set(symbol, new Set());
    }
    this.listeners.get(symbol)!.add(callback);

    this.ws?.send(JSON.stringify({ action: 'subscribe', symbol }));

    // Return cleanup function
    return () => {
      this.listeners.get(symbol)?.delete(callback);
      if (this.listeners.get(symbol)?.size === 0) {
        this.subscriptions.delete(symbol);
        this.ws?.send(JSON.stringify({ action: 'unsubscribe', symbol }));
      }
    };
  }
}

export const stockWS = new StockWebSocket();
```

## React Hook

Declarative hook for components to consume real-time data.

```typescript
import { useEffect, useState } from 'react';
import { stockWS } from '@/lib/websocket';

export function useStockTick(symbol: string) {
  const [tick, setTick] = useState<StockTick | null>(null);

  useEffect(() => {
    const unsubscribe = stockWS.subscribe(symbol, setTick);
    return unsubscribe;
  }, [symbol]);

  return tick;
}
```

## Component Usage

```tsx
export default function StockPrice({ symbol }: { symbol: string }) {
  const tick = useStockTick(symbol);

  if (!tick) return <Skeleton />;

  return (
    <div>
      <span>{tick.price.toLocaleString()} KRW</span>
      <span className={tick.change > 0 ? 'text-red-500' : 'text-blue-500'}>
        {tick.changeRate > 0 ? '+' : ''}{tick.changeRate}%
      </span>
    </div>
  );
}
```

## TanStack Query Cache Sync

Sync WebSocket data into Query cache for consistency.

```typescript
import { useQueryClient } from '@tanstack/react-query';

export function useStockTickSync(symbol: string) {
  const queryClient = useQueryClient();
  const tick = useStockTick(symbol);

  useEffect(() => {
    if (tick) {
      queryClient.setQueryData(['stock', symbol, 'price'], tick);
    }
  }, [tick, symbol, queryClient]);

  return tick;
}
```

## Data Flow

```
Backend WebSocket → StockWebSocket (singleton) → useStockTick (hook) → Component (render)
                                                → useStockTickSync → TanStack Query cache
```
