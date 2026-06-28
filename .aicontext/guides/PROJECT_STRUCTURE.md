# Project Structure

## Root

```
stockquare/
├── .aicontext/             # AI context (guides, patterns, specs)
├── backend/                # FastAPI application
├── frontend/               # Next.js application
├── docker-compose.yml      # Local development environment
├── CLAUDE.md               # Claude Code instructions
└── .gitignore
```

## Backend

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app entrypoint
│   ├── config.py           # Settings / environment config
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py         # Shared dependencies (DI)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py   # API router aggregation
│   │       ├── auth.py     # Authentication endpoints
│   │       ├── trading.py  # Order endpoints
│   │       ├── portfolio.py
│   │       └── stock.py    # Stock info / price endpoints
│   ├── kis/
│   │   ├── __init__.py
│   │   ├── client.py       # KIS HTTP client
│   │   ├── websocket.py    # KIS WebSocket client
│   │   ├── token.py        # Token manager
│   │   └── models.py       # KIS API response models
│   ├── models/
│   │   ├── __init__.py
│   │   ├── order.py        # Order domain models
│   │   ├── stock.py        # Stock domain models
│   │   └── portfolio.py    # Portfolio domain models
│   ├── services/           # Business logic, one package per domain
│   │   ├── __init__.py
│   │   ├── _helpers.py     # Shared parsing helpers (to_int / to_float)
│   │   ├── trading/        # Each domain is a package:
│   │   │   ├── __init__.py #   __init__ re-exports the public surface so
│   │   │   └── service.py  #   `from app.services.trading import TradingService`
│   │   ├── portfolio/      #   stays stable regardless of internal file layout.
│   │   │   ├── __init__.py
│   │   │   └── service.py
│   │   ├── strategy/       # A domain may hold more than one module:
│   │   │   ├── __init__.py
│   │   │   ├── service.py      # StrategyService
│   │   │   └── indicators.py   # rule evaluation (strategy-only)
│   │   └── assistant/      # AI assistant over local Claude Code (Agent SDK)
│   │       ├── __init__.py
│   │       ├── service.py  # AssistantService (chat / chat_stream / confirm)
│   │       ├── tools.py    # in-process MCP tool registry + mutate gate
│   │       └── runner.py   # Claude Agent SDK boundary
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py      # Database session
│   │   └── models.py       # SQLAlchemy / ORM models
│   └── core/
│       ├── __init__.py
│       ├── exceptions.py   # Custom exception hierarchy
│       └── logging.py      # Logging configuration
├── tests/
│   ├── conftest.py
│   ├── api/
│   ├── kis/
│   └── services/
├── pyproject.toml
├── Dockerfile
└── .env.example
```

### Layer Responsibilities

| Layer | Role | Depends On |
|-------|------|-----------|
| `api/` | HTTP endpoints, request/response | `services/`, `models/` |
| `services/` | Business logic — one package per domain | `kis/`, `db/`, `models/` |
| `kis/` | KIS API integration | External API |
| `models/` | Domain models (Pydantic) | — |
| `db/` | Database access | PostgreSQL |
| `core/` | Cross-cutting concerns | — |

### Dependency Rule

```
api → services → kis / db
         ↓
       models
```

`kis/` and `db/` must not depend on each other. `api/` must not call `kis/` directly.

### Service package convention

Each domain under `services/` is a package, not a single module. The single
entry module is named `service.py`; a domain may add sibling modules when it
grows (e.g. `strategy/indicators.py`, `assistant/tools.py`, `assistant/runner.py`).
The package `__init__.py` re-exports the public surface, so importers use the
stable `from app.services.<domain> import <Symbol>` path regardless of how the
domain is split internally. Add a new domain by creating `services/<domain>/`
with `service.py` + `__init__.py`; grow an existing one by adding modules inside
its package. Cross-domain code imports the package, never a sibling's `service.py`.

## Frontend

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Landing / redirect
│   │   ├── dashboard/
│   │   │   ├── page.tsx
│   │   │   └── _components/
│   │   ├── trading/
│   │   │   ├── page.tsx
│   │   │   └── _components/
│   │   └── portfolio/
│   │       ├── page.tsx
│   │       └── _components/
│   ├── components/
│   │   ├── ui/                 # shadcn/ui primitives
│   │   └── common/             # Shared project components
│   ├── hooks/                  # Custom hooks
│   ├── lib/
│   │   ├── api.ts              # API client (fetch wrapper)
│   │   └── websocket.ts        # WebSocket manager
│   ├── stores/                 # Zustand stores
│   └── types/                  # TypeScript type definitions
├── public/
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── Dockerfile
└── .env.example
```

### Directory Roles

| Directory | Role |
|-----------|------|
| `app/` | Pages and routing (Next.js App Router) |
| `app/*/_components/` | Page-local components |
| `components/ui/` | shadcn/ui base components |
| `components/common/` | Shared components across pages |
| `hooks/` | Reusable custom hooks |
| `lib/` | Utilities, API client, WebSocket |
| `stores/` | Zustand state stores |
| `types/` | Shared TypeScript interfaces/types |
