# Git Convention

## Commit Message

```
<type>(<scope>): <description>
```

### Types

| Type | Usage | Example |
|------|-------|---------|
| `feat` | New feature | `feat(trading): add market order endpoint` |
| `fix` | Bug fix | `fix(kis): handle token refresh race condition` |
| `refactor` | Code restructure (no behavior change) | `refactor(api): extract common request wrapper` |
| `docs` | Documentation | `docs: add API integration pattern` |
| `test` | Add or update tests | `test(strategy): add moving average unit tests` |
| `chore` | Build, config, dependencies | `chore: update FastAPI to 0.115` |
| `style` | Formatting (no logic change) | `style: apply ruff formatting` |

### Scopes

| Scope | Area |
|-------|------|
| `kis` | KIS API integration |
| `trading` | Order execution |
| `strategy` | Trading strategy engine |
| `portfolio` | Portfolio management |
| `auth` | Authentication |
| `ui` | Frontend UI |
| `chart` | Chart components |
| `ws` | WebSocket / realtime |

Scope is optional. Omit when a change spans multiple areas.

### Rules

- Use lowercase after the type prefix
- Use imperative mood (`add` not `added`)
- No trailing period
- Keep subject line under 72 characters
- Add body for non-obvious changes (separated by blank line)

```
feat(trading): add limit order support

KIS API tr_id TTTC0802U for limit buy orders.
Includes price validation against daily price limits.
```

## Branch Strategy

- `main` — stable, deployable state
- Feature branches from `main`:

```
feat/market-order
feat/realtime-chart
fix/token-refresh
refactor/kis-client
```

### Rules

- Branch names: `<type>/<short-description>` in kebab-case
- Merge via squash merge to keep `main` history clean
- Delete branch after merge

## Commit Granularity

- One logical change per commit
- Do not mix backend and frontend changes in a single commit when possible
- Separate refactoring from feature work
