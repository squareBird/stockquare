# Stockquare Backend

FastAPI backend for Stockquare, powered by the KIS Open API.

## Stack

- Python 3.12
- FastAPI + Uvicorn
- httpx (KIS HTTP client)
- SQLAlchemy (async) + asyncpg (Postgres) / aiosqlite (dev)
- Pydantic v2 + pydantic-settings

## Quick Start

### 1. Configure environment

Copy `.env.example` to `.env` and fill in your KIS credentials.

```sh
cp .env.example .env
```

Required variables:

- `KIS_APP_KEY`, `KIS_APP_SECRET` — issued from the KIS Open API portal
- `KIS_ACCOUNT_NO` — 8-digit account number
- `KIS_ACCOUNT_PRODUCT_CODE` — 2-digit product code (usually `01`)
- `KIS_ACCOUNT_MODE` — `mock` or `real`
- `DATABASE_URL` — e.g. `postgresql+asyncpg://user:pw@host:5432/stockquare` or `sqlite+aiosqlite:///./stockquare.db`

### 2. Run locally (uv)

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000/health> to verify the server is up.

Interactive API docs: <http://localhost:8000/docs>

### 3. Run via Docker

```sh
docker build -t stockquare-backend:latest .
docker run --rm -p 8000:8000 --env-file .env stockquare-backend:latest
```

The image does **not** bake in `.env`. Inject secrets at runtime via `--env-file` or `-e`.

## Testing & Linting

```sh
.venv/bin/ruff check app tests
.venv/bin/ruff format app tests
.venv/bin/pytest
```

All tests mock KIS API calls via `tests/conftest.py::FakeKISClient`. The DB layer uses an in-memory SQLite instance per test.

## Project Layout

```
backend/
├── app/
│   ├── api/v1/      # HTTP routes (auth.py, dashboard.py, router.py)
│   ├── core/        # Config + exception hierarchy
│   ├── db/          # SQLAlchemy engine, session, ORM models
│   ├── kis/         # KIS HTTP client, token manager, Pydantic models
│   ├── models/      # Domain Pydantic models (watchlist)
│   ├── services/    # Business logic (dashboard)
│   └── main.py      # FastAPI app factory
├── tests/           # Mirrors app/ layout
├── Dockerfile
├── .dockerignore
├── .env.example
└── pyproject.toml
```

See `.aicontext/spec/backend/AUTH.md` and `.aicontext/spec/backend/DASHBOARD.md` for the detailed API specification.

## Endpoints

### Auth

- `POST /api/v1/auth/token` — issue/refresh a KIS OAuth access token
- `GET  /api/v1/auth/status` — inspect the in-memory token state
- `POST /api/v1/auth/revoke` — revoke the active token

### Portfolio

- `GET  /api/v1/portfolio/summary`

### Watchlist

- `GET    /api/v1/watchlist`
- `POST   /api/v1/watchlist`
- `PATCH  /api/v1/watchlist/reorder`
- `DELETE /api/v1/watchlist/{item_id}`

### Market

- `GET /api/v1/market/indices`

### Stocks

- `GET /api/v1/stocks/search?q={query}&limit={n}`

### Health

- `GET /health`
