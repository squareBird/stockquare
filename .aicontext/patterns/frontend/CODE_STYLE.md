# Frontend Code Style

Based on Airbnb JavaScript Style Guide. Enforced by ESLint + Prettier.

> Reference: https://github.com/airbnb/javascript

## Formatter & Linter

- **ESLint** — `eslint-config-next` (flat config) + project rule overrides
- **Prettier** — code formatting

Next.js 16 removed `next lint`, so we use ESLint 9 flat config
(`eslint.config.mjs`). The Airbnb shareable configs are eslintrc-format and
unmaintained for ESLint 9, so they are no longer extended; the custom rules we
relied on (`import/order`, `@typescript-eslint/no-unused-vars` with `^_` ignore,
`no-console`) are declared explicitly. The intent below (naming, import order,
TS strict, no `any`) is unchanged.

```js
// eslint.config.mjs
import nextPlugin from 'eslint-config-next';
import prettierConfig from 'eslint-config-prettier';

export default [
  { ignores: ['.next/**', 'node_modules/**', 'out/**', 'build/**', 'next-env.d.ts'] },
  ...nextPlugin, // next + next/typescript (react, react-hooks, import, jsx-a11y, @next/next)
  {
    files: ['**/*.{js,jsx,mjs,ts,tsx,mts,cts}'],
    rules: {
      /* project overrides: import/order, no-unused-vars, no-console, react/* */
    },
  },
  { rules: prettierConfig.rules }, // Prettier compatibility (must be last)
];
```

Run lint with `pnpm lint` (`eslint .`); lint a single file with
`./node_modules/.bin/eslint <file>` from `frontend/`.

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
