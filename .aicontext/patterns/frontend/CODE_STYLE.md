# Frontend Code Style

Based on Airbnb JavaScript Style Guide. Enforced by ESLint + Prettier.

> Reference: https://github.com/airbnb/javascript

## Formatter & Linter

- **ESLint** — `eslint-config-airbnb-typescript` + Next.js built-in rules
- **Prettier** — code formatting

```json
// .eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "next/typescript",
    "airbnb",
    "airbnb-typescript",
    "prettier"
  ],
  "parserOptions": {
    "project": "./tsconfig.json"
  }
}
```

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2
}
```

## Naming

| Target | Convention | Example |
|--------|-----------|---------|
| Component | PascalCase | `StockChart.tsx` |
| Function/Variable | camelCase | `getStockPrice()`, `accessToken` |
| Constant | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Type/Interface | PascalCase | `StockPrice`, `OrderRequest` |
| Custom Hook | `use` prefix | `useStockPrice()` |
| Boolean Variable | `is`/`has`/`should` prefix | `isLoading`, `hasError` |

## TypeScript

Use strict mode. Never use `any`.

```typescript
// Good
interface StockPrice {
  symbol: string;
  price: number;
  change: number;
  changeRate: number;
}

// Bad
const data: any = response.data;
```

## Component

Use function declarations with default export.

```tsx
interface StockCardProps {
  symbol: string;
  price: number;
}

export default function StockCard({ symbol, price }: StockCardProps) {
  return (
    <div>
      <span>{symbol}</span>
      <span>{price.toLocaleString()}</span>
    </div>
  );
}
```

## Import Order

Automatically sorted by ESLint:

1. React / Next.js (`react`, `next`)
2. Third-party (`zustand`, `@tanstack/react-query`)
3. Local absolute paths (`@/components`, `@/hooks`)
4. Relative paths (`./StockCard`)
5. Styles (`./styles.module.css`)

```typescript
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import { useQuery } from '@tanstack/react-query';

import { StockPrice } from '@/types/stock';
import { fetchStockPrice } from '@/lib/api';

import StockCard from './StockCard';
```

## General Rules

- One component per file
- Arrow functions for callbacks/utilities only; use function declarations for components
- No nested ternary operators (use early return or variable extraction)
- Always use `===` (never `==`)
- Use optional chaining (`?.`)
