# Stockquare Frontend

Next.js 14 App Router dashboard for the Stockquare trading system.

## Stack

- Next.js 14 (App Router, TypeScript strict)
- Tailwind CSS 3.4
- TanStack Query v5 (server state)
- Zustand v5 (client state)
- ESLint (Airbnb + Next.js) + Prettier

## Project Layout

```
src/
├── app/
│   ├── dashboard/
│   │   ├── _components/    # Page-local client components
│   │   ├── _hooks/         # Page-local hooks (e.g. polling interval)
│   │   └── page.tsx
│   ├── layout.tsx
│   ├── page.tsx            # Redirects to /dashboard
│   ├── providers.tsx       # TanStack Query provider
│   └── globals.css
├── components/common/      # Shared display components
├── lib/
│   ├── api/                # Fetch client, adapters, mock fallback
│   ├── format.ts           # Number / currency formatters
│   ├── market-hours.ts     # Korean market-hours helper
│   └── query-client.ts
├── stores/                 # Zustand stores
└── types/                  # Shared TypeScript types
```

## Local development

### Prerequisites

- Node.js ≥ 20
- pnpm (via corepack: `corepack enable pnpm`)

### Setup

```bash
# 1. Copy the example env file and fill in your values
cp .env.example .env.local

# 2. Install dependencies
pnpm install

# 3. Run the dev server
pnpm dev
```

The dev server listens on `http://localhost:3000`. The root page redirects to `/dashboard`.

### Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL | `http://localhost:8000` |
| `NEXT_PUBLIC_USE_MOCK` | Use in-memory mock data (dev only). `true` bypasses the backend. | `false` |

Mocks only activate when `NEXT_PUBLIC_USE_MOCK=true` **and** `NODE_ENV !== 'production'`. Production images always ignore the flag.

### Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start the Next.js dev server |
| `pnpm build` | Production build |
| `pnpm start` | Start the production server (requires a prior `build`) |
| `pnpm lint` | Run ESLint |
| `pnpm typecheck` | Run `tsc --noEmit` in strict mode |

## Docker

The image is a multi-stage build that outputs a Next.js standalone bundle, runs as a non-root user, and listens on port 3000.

### Build

```bash
docker build -t stockquare-frontend:latest .
```

To override the API base URL at build time:

```bash
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.com \
  -t stockquare-frontend:latest .
```

> `NEXT_PUBLIC_*` variables are inlined at build time — they cannot be changed after the image is built.

### Run

```bash
docker run --rm -p 3000:3000 stockquare-frontend:latest
```

Then open http://localhost:3000.

### Notes

- `.env` and `.env.*` files are **never** baked into the image (see `.dockerignore`).
- Mock data is disabled in production builds (`NEXT_PUBLIC_USE_MOCK=false`).
- Telemetry is disabled (`NEXT_TELEMETRY_DISABLED=1`).
