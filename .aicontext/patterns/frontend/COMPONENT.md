# Component Pattern

Component design patterns for Next.js App Router.

## Server vs Client Components

Default to Server Components. Use Client Components only when interactivity is needed.

| Feature | Server Component | Client Component |
|---------|-----------------|-----------------|
| Data fetching | Yes | No (use TanStack Query) |
| Event handlers | No | Yes |
| useState/useEffect | No | Yes |
| Browser APIs | No | Yes |

```
app/
├── dashboard/
│   ├── page.tsx               # Server Component (layout, initial data)
│   └── _components/
│       ├── PortfolioCard.tsx   # Client Component ('use client')
│       └── StockList.tsx       # Client Component ('use client')
```

## File Structure

Page-local components go in `_components/`. Shared components go in `@/components/`.

```
frontend/
├── src/
│   ├── app/
│   │   ├── dashboard/
│   │   │   ├── page.tsx
│   │   │   └── _components/
│   │   └── trading/
│   │       ├── page.tsx
│   │       └── _components/
│   └── components/            # Shared components
│       ├── ui/                # shadcn/ui based
│       └── common/            # Project-wide shared
```

## Props Definition

Define props with `interface` at the top of the file.

```tsx
interface OrderFormProps {
  symbol: string;
  currentPrice: number;
  onSubmit: (order: OrderRequest) => void;
}

export default function OrderForm({ symbol, currentPrice, onSubmit }: OrderFormProps) {
  ...
}
```

## Conditional Rendering

Use ternary only for simple cases. For complex conditions, use early return or variable extraction.

```tsx
// Good — simple condition
{isLoading ? <Skeleton /> : <StockPrice price={price} />}

// Good — complex condition extracted
function OrderStatus({ status }: { status: OrderStatusType }) {
  if (status === 'pending') return <Badge variant="warning">Pending</Badge>;
  if (status === 'filled') return <Badge variant="success">Filled</Badge>;
  return <Badge variant="destructive">Cancelled</Badge>;
}
```

## Custom Hook Extraction

Extract complex logic from components into custom hooks.

```typescript
// hooks/useStockWebSocket.ts
export function useStockWebSocket(symbol: string) {
  const [price, setPrice] = useState<number>(0);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/stock/${symbol}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrice(data.price);
    };
    return () => ws.close();
  }, [symbol]);

  return { price };
}
```
