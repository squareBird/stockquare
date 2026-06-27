# Deployment

Stockquare is a **personal, local-first** trading system: each user runs their
own instance on their own machine, against their own KIS account and (for the AI
assistant) their own Claude Code login. It is **not** a multi-tenant hosted
service.

## 1. Components

| Component | What it is | Where it can run |
|-----------|------------|------------------|
| **backend** | FastAPI app; talks to KIS Open API and (for AI) the local Claude Code | local process **or** Docker (see §3 constraint) |
| **frontend** | Next.js app | local process **or** Docker |
| **db** | PostgreSQL | local process **or** Docker |
| **Claude Code** | The user's locally-installed Claude CLI, used by the AI assistant | **local host only** (prerequisite) |

## 2. Prerequisites

- Python 3.12, Node.js (frontend), PostgreSQL (or the Docker image).
- KIS Open API credentials (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_ACCOUNT_NO`) —
  optional in dev; required for live data/trading.
- **For the AI assistant only:** the user's own **Claude Code** installed and
  logged in on the host machine.
  - The backend drives Claude Code through the **Claude Agent SDK**
    (`pip install claude-agent-sdk`, Python ≥ 3.10) — see backend
    `spec/backend/ASSISTANT.md`.
  - Authentication uses **whatever the local `claude` CLI is logged in with**
    (the user's own Claude subscription). No `ANTHROPIC_API_KEY` is required for
    the default flow; an API key (or Bedrock/Vertex/Foundry provider) is an
    optional override.
  - **ToS:** Stockquare does not offer Claude login to third parties — each user
    authenticates **their own** Claude Code. This is the boundary that keeps the
    local-first design within Anthropic's terms; do not repackage it as a hosted
    multi-user service without revisiting this.
  - If Claude Code is absent or not logged in, the assistant endpoints return
    503 `ASSISTANT_NOT_CONFIGURED` and the rest of the app works normally.

## 3. Deployment topologies

Both supported topologies keep **backend on the local host**. This is a hard
constraint, not a preference (§4).

### Topology A — All local

backend, frontend, and PostgreSQL all run as local processes. Simplest for
development and for using the AI assistant.

```
[ localhost ]
  frontend  :3000  ─┐
  backend   :8000  ─┼─ all on the host
  postgres  :5432  ─┘
  claude code (CLI, logged in)
```

### Topology B — Local backend + Dockerized frontend/db

backend runs locally (so it can reach the host's Claude Code); frontend and
PostgreSQL run in Docker and connect back to the host via port forwarding.

```
[ localhost ]                 [ Docker ]
  backend  :8000  ◀───────────  frontend :3000   (NEXT_PUBLIC_API_BASE_URL → host:8000)
  claude code (CLI)             postgres :5432  ──▶ backend connects to localhost:5432
```

- Frontend container: `NEXT_PUBLIC_API_BASE_URL` must point at the **host**
  (e.g. `http://localhost:8000` from the browser, or `http://host.docker.internal:8000`
  where the container itself must reach it).
- Backend (local) connects to the Dockerized Postgres on `localhost:5432`
  (the compose file already publishes `5432:5432`).

## 4. Why backend stays local (AI assistant constraint)

The Claude Agent SDK spawns / communicates with the **local `claude` CLI as a
subprocess in the backend's own environment**, using the credentials in the
host's `~/.claude`. Therefore:

- If the backend runs in Docker, Claude Code and its login must also be present
  **inside** that container — an awkward, fragile setup that defeats the
  local-first model. **Do not run the backend in Docker when the AI assistant is
  enabled.**
- The current `docker-compose.yml` builds a **backend** container. For the
  AI-enabled setup, run the backend locally instead and use compose only for
  `postgres` (and optionally `frontend`):

  ```bash
  # AI-enabled: DB (and optionally frontend) in Docker, backend local
  docker compose up -d postgres
  # then run the backend on the host:
  cd backend && uvicorn app.main:app --reload --port 8000
  ```

- A future compose change should split the backend into an **optional profile**
  so `docker compose up` does not start a backend container in the AI-enabled
  topology. (Tracked as a follow-up; not part of the Phase 1 assistant work.)

> Non-AI deployments (no assistant) may still run the backend in Docker exactly
> as `docker-compose.yml` does today — the local-backend constraint applies
> **only** when the AI assistant is in use.

## 5. Security notes (AI assistant)

The assistant runs on the user's machine through Claude Code, so the tool
surface is locked down (enforced in code per `spec/backend/ASSISTANT.md` §5.2):

- Built-in Claude Code tools (Bash, Read, Write, Edit, WebFetch, …) are
  **disabled** (`tools=[]`); only the in-process Stockquare MCP tools are exposed.
- The user's `~/.claude` settings, `CLAUDE.md`, and skills are **not** loaded
  into the assistant agent (`setting_sources=[]`).
- Mutating tools (e.g. watchlist add) require an explicit client confirmation
  turn; the model can never execute them inline.
- `permission_mode` is `default` — never `bypassPermissions` / `acceptEdits`.

## 6. Configuration summary

| Variable | Used by | Notes |
|----------|---------|-------|
| `DATABASE_URL` | backend | Postgres DSN (compose overrides the sqlite default). |
| `KIS_APP_KEY` / `KIS_APP_SECRET` / `KIS_ACCOUNT_NO` | backend | KIS creds; optional in dev. |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | Must resolve to the (local) backend from the browser. |
| `ASSISTANT_ENABLED` | backend | Feature kill switch (default `true`). |
| `ASSISTANT_MODEL` | backend | Model alias for the SDK (default `haiku`). |
| `ASSISTANT_MAX_TURNS` | backend | SDK tool-loop cap (default `5`). |
| `ASSISTANT_CLI_PATH` | backend | Optional override for the `claude` executable path. |
| `ANTHROPIC_API_KEY` | backend | **Optional** override; default flow uses the local Claude Code login. |

See `spec/backend/ASSISTANT.md` for the full assistant settings table and
runtime readiness probe.
