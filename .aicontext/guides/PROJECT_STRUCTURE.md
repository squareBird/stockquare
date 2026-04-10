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
│   ├── services/
│   │   ├── __init__.py
│   │   ├── trading.py      # Trading business logic
│   │   ├── portfolio.py    # Portfolio business logic
│   │   └── strategy.py     # Auto-trading strategy engine
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
| `services/` | Business logic | `kis/`, `db/`, `models/` |
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
