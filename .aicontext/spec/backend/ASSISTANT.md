# Assistant Spec (Backend)

A conversational AI assistant that turns natural-language requests into actions
against the existing Stockquare API. The user types a message (e.g. "등락률
상위 조건으로 추천종목 알려줘", "추천 종목들 관심종목에 추가해줘"); the
assistant reasons over the request, calls **tools** that wrap existing services,
and replies in Korean. The assistant is the *orchestration* layer — it owns no
business logic of its own; every effect goes through an existing service.

> **Execution model.** The assistant does **not** call the Anthropic API
> directly. It runs the user's **locally-installed Claude Code** through the
> **Claude Agent SDK for Python** (`claude-agent-sdk`). The backend hosts an
> in-process MCP server whose tools wrap existing services; Claude Code drives
> the agent loop and calls those tools. This is a **local-first** design: the
> backend and Claude Code run on the same machine, under the user's own Claude
> login. See `DEPLOYMENT.md` for the deployment contract and prerequisites.

> **Safety stance.** Read tools (recommend, search, quote, ranking, chart,
> watchlist read, account/holdings) run freely. **Mutating tools** (watchlist
> add / remove) are never executed inline — the assistant *proposes* them and
> the client must send an explicit confirmation turn before they run.
> Trading/order placement is **out of scope for Phase 1** and no order tool is
> registered. Claude Code's built-in tools (Bash, Read,
> Write, Edit, WebFetch, …) are **fully disabled**; the model may only call the
> Stockquare MCP tools (§2.1).

## 0. Concepts

| Term | Meaning |
|------|---------|
| **Conversation** | An ordered list of `messages` the client sends on every turn (stateless server; the client owns history). |
| **Tool** | A typed capability the model may call. Each tool wraps one existing service method, exposed via the in-process MCP server. Tools are `read` or `mutate`. |
| **Agent loop** | The Claude Agent SDK runs the model → tool_use → tool_result → model loop **inside Claude Code**; the backend does not hand-roll it. Bounded by `assistant_max_turns`. |
| **Proposed action** | A `mutate` tool the model wants to run. The `can_use_tool` permission callback **denies** it and records a `pending_action` for confirmation instead of executing it. |
| **Confirmation turn** | A follow-up request carrying the `pending_action` the user approved; the server executes the wrapped service **directly, without invoking the model**. |
| **Turn collector** | A request-scoped object the tool handlers write to (recommendations, tool-call results, pending actions). The service reads it after the loop to build the response. |

## 1. Endpoints

All assistant endpoints live under `/api/v1/assistant`. **The wire contract
(request/response shapes) is unchanged from the API-key design**, so the
frontend spec (`frontend/ASSISTANT.md`) applies as-is — only the server-side
execution mechanism changed.

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/api/v1/assistant/chat` | Send a conversation; get the assistant's reply, any tool activity, and any pending actions. |
| POST   | `/api/v1/assistant/confirm` | Execute a previously proposed `mutate` action the user approved. |

Phase 1 is **non-streaming** (single JSON response). Streaming (SSE) is a
Phase 2 extension (Section 9).

### POST /api/v1/assistant/chat

**Request**
```json
{
  "messages": [
    { "role": "user", "content": "등락률 상위 조건으로 추천종목 5개 알려줘" }
  ]
}
```

```python
class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=4000)

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
```

**Response (`200 OK`)**
```json
{
  "reply": "등락률 상위 5개 종목입니다:\n1. ...",
  "tool_calls": [
    { "tool": "rank_stocks", "input": { "by": "fluctuation", "limit": 5 }, "ok": true }
  ],
  "pending_actions": [],
  "recommendations": [
    { "symbol": "005930", "name": "삼성전자", "price": 72000, "change_rate": 5.1, "reason": "등락률 상위" }
  ]
}
```

When the model proposes a mutation, `reply` asks for confirmation and the action
is surfaced (not executed):
```json
{
  "reply": "삼성전자, SK하이닉스 2종목을 관심종목에 추가할까요?",
  "tool_calls": [],
  "pending_actions": [
    {
      "id": "act_1",
      "tool": "add_to_watchlist",
      "summary": "관심종목에 2종목 추가: 005930, 000660",
      "input": { "symbols": ["005930", "000660"] }
    }
  ],
  "recommendations": []
}
```

```python
class ToolCallResult(BaseModel):
    tool: str
    input: dict
    ok: bool
    error_code: str | None = None      # StockquareError code on failure

class PendingAction(BaseModel):
    id: str                            # opaque, stable within this response
    tool: str                          # bare tool name, e.g. "add_to_watchlist"
    summary: str                       # human-readable, Korean
    input: dict                        # exact arguments to execute on confirm

class Recommendation(BaseModel):
    symbol: str
    name: str
    price: int | None = None
    change_rate: float | None = None
    reason: str                        # why the assistant surfaced it

class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallResult]
    pending_actions: list[PendingAction]
    recommendations: list[Recommendation]
```

> **Tool naming on the wire.** Inside the SDK, tools are namespaced
> `mcp__stockquare__<tool>` (§2.1). On the **wire** (`tool_calls[].tool`,
> `pending_actions[].tool`) the bare name (`rank_stocks`, `add_to_watchlist`) is
> used so the client and the `/confirm` registry stay decoupled from the MCP
> prefix.

### POST /api/v1/assistant/confirm

Executes one approved mutate action. The client echoes back the
`PendingAction` it received. The server is stateless and **re-validates the
input against the tool's Pydantic schema before running it — it never invokes
the model on confirm**; it calls the wrapped service directly.

**Request**
```json
{
  "action": {
    "id": "act_1",
    "tool": "add_to_watchlist",
    "summary": "관심종목에 2종목 추가: 005930, 000660",
    "input": { "symbols": ["005930", "000660"] }
  }
}
```

**Response (`200 OK`)**
```json
{
  "ok": true,
  "tool": "add_to_watchlist",
  "result": { "added": ["005930", "000660"], "skipped": [] },
  "message": "2종목을 관심종목에 추가했습니다."
}
```

```python
class ConfirmRequest(BaseModel):
    action: PendingAction

class ConfirmResponse(BaseModel):
    ok: bool
    tool: str
    result: dict
    message: str
```

Only tools declared `mutate` may be confirmed. A `read` tool or an unknown tool
name → 400 `INVALID_ACTION`.

## 2. Tools

Each tool maps to exactly one existing service call. The tool registry is the
**only** surface the model can affect the system through — built-in Claude Code
tools are disabled (§5.2).

Tools are grouped by domain (lookup / chart / watchlist / portfolio) so the
model — and the registry in `assistant/tools.py` — reason about capabilities by
area.

| Domain | Tool | Kind | Wraps | Purpose |
|--------|------|------|-------|---------|
| Lookup | `rank_stocks` | read | `stocks.rank_stocks` (§3 KIS ranking) | Condition-based recommendation: top stocks by fluctuation / volume. |
| Lookup | `search_stocks` | read | `stocks.search_stocks` | Resolve a name/keyword → symbols. |
| Lookup | `get_quote` | read | `stocks.get_quote` (KIS `inquire-price`) | Current price/change for a symbol. |
| Chart | `get_chart` | read | `stocks.get_history` | Open the symbol's chart in the Trading tab (emits an `open_chart` view action) and return a compact trend summary. Candle granularity `interval` = `min`/`day`/`week`/`month`, default `day`. |
| Watchlist | `list_watchlist` | read | `watchlist.list_watchlist` | Read the user's current watchlist. |
| Watchlist | `add_to_watchlist` | **mutate** | `watchlist.add_watchlist` (per symbol) | Add one or more symbols to the watchlist. |
| Watchlist | `remove_from_watchlist` | **mutate** | `watchlist.delete_watchlist_by_symbol` (per symbol) | Remove one or more symbols from the watchlist. |
| Portfolio | `get_account_summary` | read | `portfolio.get_account_summary` | Total asset, daily profit, cash balance, holdings count. |
| Portfolio | `list_holdings` | read | `holdings.get_holdings` | Current holdings with quantity, avg price, current price, profit. |

`add_to_watchlist` / `remove_from_watchlist` accept a list but execute
per-symbol through the existing `WatchlistService`. `add_watchlist` enforces the
20-item cap, duplicate rejection, and symbol validation; `delete_watchlist_by_symbol`
resolves the row by its 6-digit symbol (the assistant only knows symbols, not DB
ids). Per-symbol failures are collected into `result.skipped` (`added` /
`removed` for the success list) with their `error_code`; partial success still
returns `ok: true`.

### 2.1 Tool definition (Claude Agent SDK, in-process MCP server)

Tools are declared with the SDK `@tool` decorator and bundled into a single
in-process MCP server with `create_sdk_mcp_server`. The server runs **inside the
backend process** (no subprocess, no network) — the handler is a plain Python
async function that calls the existing service.

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ToolAnnotations

@tool(
    "rank_stocks",
    "Return top KRX stocks ranked by a condition. Use for recommendation "
    "requests like '등락률 상위 종목 추천'.",
    {  # full JSON Schema dict — required for enums/ranges/defaults
        "type": "object",
        "properties": {
            "by": {"type": "string", "enum": ["fluctuation", "volume"]},
            "direction": {"type": "string", "enum": ["up", "down"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["by"],
    },
    annotations=ToolAnnotations(readOnlyHint=True),  # allows parallel read calls
)
async def rank_stocks(args: dict) -> dict:
    params = RankStocksArgs(**args)              # Pydantic re-validation
    ranked = await stocks_service.rank_stocks(...)
    collector.add_recommendations(ranked)        # request-scoped collector (§4)
    collector.record_call("rank_stocks", args, ok=True)
    return {"content": [{"type": "text", "text": _summarize(ranked)}]}

stockquare_server = create_sdk_mcp_server(
    name="stockquare", version="1.0.0",
    tools=[
        # lookup
        rank_stocks, search_stocks, get_quote,
        # chart
        get_chart,
        # watchlist
        list_watchlist, add_to_watchlist, remove_from_watchlist,
        # portfolio
        get_account_summary, list_holdings,
    ],
)
```

Notes that drive the design:

- **Re-validate inside the handler.** The dict schema is for the model; the
  handler re-parses `args` with a Pydantic model before calling the service
  (never trust model output directly). On schema/validation failure the handler
  returns `{"content": [...], "is_error": True}` so the loop continues and the
  model can retry — it must **not** raise (an uncaught exception aborts the whole
  `query()` call).
- **`@tool` forwards only `content` and `is_error`** (Python in-process server
  limitation — `structuredContent` is dropped). Therefore structured results
  (recommendations) are **not** returned through the tool result; the handler
  pushes them into the request-scoped **turn collector** (§4), and the service
  reads the collector after the loop. The `content` text is only what the model
  reasons over.
- **`read` tools** set `readOnlyHint=True` so Claude can batch them in parallel.
  `add_to_watchlist` leaves the default (`destructiveHint=True`) and is gated by
  the permission callback (§4.1) — it is **never** placed in `allowed_tools`.

## 3. KIS Ranking (new capability in `stocks`)

Recommendation needs market-wide ranking, which the codebase does not yet have.
Add a `rank_stocks` method to the **stocks service** (not a new domain) so the
assistant and any future screener reuse one path.

| Ranking | KIS Endpoint | tr_id | Key fields |
|---------|--------------|-------|-----------|
| 등락률 순위 (fluctuation) | `/uapi/domestic-stock/v1/ranking/fluctuation` | `FHPST01700000` | `stck_shrn_iscd`, `stck_prpr`, `prdy_ctrt` |
| 거래량 순위 (volume) | `/uapi/domestic-stock/v1/quotations/volume-rank` | `FHPST01710000` | `stck_shrn_iscd`, `stck_prpr`, `acml_vol` |

> **tr_id verification note.** `FHPST01700000` / `FHPST01710000` are the
> commonly-documented ranking tr_ids but must be verified against
> `koreainvestment/open-trading-api` (`examples_llm/`, `legacy/rest/`) before
> merge — same discipline as `TRADING.md` / `STRATEGY.md`. A mismatch surfaces
> as `rt_cd != "0"` and is captured by `_log_kis_error_body`.

```python
class RankedStock(BaseModel):
    symbol: str
    name: str                  # resolved from the master index
    price: int
    change_rate: float
    volume: int | None = None

class RankBy(str, Enum):
    FLUCTUATION = "fluctuation"
    VOLUME = "volume"
```

Names are resolved from the in-memory master index (same pattern as
`WATCHLIST.md` §2). On KIS failure the method raises the existing
`KISAPIError` / `KISNotConfiguredError` — the tool handler catches it and
returns `is_error: True` with the `error_code` recorded in the collector,
rather than letting it abort the whole chat.

## 4. Agent Loop (delegated to the Claude Agent SDK)

The backend does **not** implement the tool loop. It configures the SDK and
iterates the message stream:

```
1. Build a request-scoped TurnCollector.
2. Build ClaudeAgentOptions:
     - mcp_servers   = {"stockquare": stockquare_server}
     - allowed_tools = the READ tools only, namespaced mcp__stockquare__*:
                        rank_stocks, search_stocks, get_quote, get_chart,
                        list_watchlist, get_account_summary, list_holdings
       (the mutate tools add_to_watchlist / remove_from_watchlist are
        intentionally NOT pre-approved — they fall through to can_use_tool)
     - tools          = []          # remove ALL built-in tools from context
     - permission_mode = "default"  # unmatched tools → can_use_tool
     - can_use_tool   = mutate_gate (§4.1)
     - system_prompt  = static Korean system prompt (§4.2)
     - max_turns      = assistant_max_turns
     - model          = assistant_model (alias, e.g. "haiku")
     - setting_sources = []         # do NOT load user ~/.claude or project settings
3. Translate ChatRequest.messages into the SDK prompt:
     - The latest user message is the prompt.
     - Prior turns are replayed via session resume OR a serialized transcript
       (Phase 1 choice: see §4.3).
4. async for message in query(prompt, options):
     - AssistantMessage  → accumulate text blocks into `reply`
     - ToolUseBlock      → (handler already ran; collector recorded it)
     - ResultMessage     → loop done; `result` is the final text
5. Build ChatResponse from `reply` + collector (tool_calls, recommendations,
   pending_actions).
```

- The loop budget (`assistant_max_turns`) bounds tool round-trips; on a
  `ResultMessage` with `subtype != "success"` (e.g. max turns / error during
  execution) the best partial `reply` is returned with a note appended.
- Recommendations surfaced by `rank_stocks` / `search_stocks` are collected by
  their handlers into `collector.recommendations` so the client renders cards
  independent of the prose `reply`.

### 4.1 Mutation gate — `can_use_tool` callback

When the model calls a mutate tool (`mcp__stockquare__add_to_watchlist` or
`mcp__stockquare__remove_from_watchlist`), it is **not** in `allowed_tools`, so
(in `permission_mode="default"`) the SDK routes the call to the `can_use_tool`
callback. The callback **denies** execution and records a `PendingAction`
instead:

```python
async def mutate_gate(tool_name, input, context):
    if tool_name == "mcp__stockquare__add_to_watchlist":
        args = AddToWatchlistArgs(**input)        # re-validate
        collector.add_pending_action(tool="add_to_watchlist", summary=_summ(args),
                                     input=args.model_dump())
        return PermissionResultDeny(message="Awaiting explicit user confirmation; "
                                            "do not retry. Ask the user to confirm in Korean.")
    if tool_name == "mcp__stockquare__remove_from_watchlist":
        args = RemoveFromWatchlistArgs(**input)   # re-validate
        collector.add_pending_action(tool="remove_from_watchlist", summary=_summ(args),
                                     input=args.model_dump())
        return PermissionResultDeny(message="Awaiting explicit user confirmation; "
                                            "do not retry. Ask the user to confirm in Korean.")
    # Any other unexpected tool is denied outright.
    return PermissionResultDeny(message="Tool not permitted.")
```

The model receives the denial as a tool_result, stops retrying, and produces a
Korean confirmation prompt as its final `reply`. The `pending_action` is
returned to the client, which renders a confirm gate. **Execution happens only
on `/confirm`, which bypasses the model entirely** and calls the matching
`WatchlistService` method (`add_watchlist` / `delete_watchlist_by_symbol`)
directly after re-validating the echoed input.

> Exact callback signature and the `PermissionResultAllow` / `PermissionResultDeny`
> types must be confirmed against the SDK reference
> (https://code.claude.com/docs/en/agent-sdk/permissions and
> `/en/agent-sdk/user-input`) at implementation; behavior above is the contract.

### 4.2 System prompt

Static, instructs the model to: answer in Korean; use the Stockquare tools and
nothing else; cite symbols by code+name; keep replies concise; never claim a
mutation succeeded. It enumerates the four tool domains (lookup / chart /
watchlist / portfolio) so the model knows its capabilities. **Critically, it
must tell the model to actually *call* the mutate tool** (`add_to_watchlist` /
`remove_from_watchlist`) when the user requests it — not to ask for confirmation
in prose. The confirmation gate is the `can_use_tool` deny (§4.1);
if the model only asks in text without calling the tool, no `pending_action` is
produced and the client renders no confirm gate. Defined once and reused every
turn.

### 4.2.1 Streaming-mode prompt (SDK constraint)

The `can_use_tool` callback **requires streaming mode**: the SDK rejects a
plain-string prompt when `can_use_tool` is set. The runner therefore passes the
prompt as a single-message `AsyncIterable[dict]`:
```python
async def _single_user_prompt(text):
    yield {"type": "user", "message": {"role": "user", "content": text},
           "parent_tool_use_id": None, "session_id": "default"}
```
This is unidirectional streaming (all input upfront), not interactive — the loop
still returns one final reply per turn.

### 4.3 Conversation continuity

Phase 1 is stateless on the server. Two viable mappings of the client-owned
history onto the SDK:

- **(a) Single-prompt replay** — fold prior turns into the prompt text each
  call via `query()`. Simplest; no session state. **Phase 1 default.**
- **(b) Session resume** — capture `session_id` from the `init` SystemMessage
  and pass `resume=session_id` on later turns. Lower latency / better context
  but introduces local session state. Deferred to Phase 2 alongside streaming.

## 5. Claude Agent SDK Integration

- SDK: `claude-agent-sdk` (Python ≥ 3.10; project is 3.12 — OK). Async API.
- The SDK spawns / talks to the **local Claude Code CLI**. Claude Code must be
  installed and authenticated on the host (prerequisite — see `DEPLOYMENT.md`).
- **No tool loop, no prompt-cache management, no manual Anthropic SDK** — the
  SDK and Claude Code own all of that.

### 5.1 Authentication

The assistant uses **whatever credentials the local Claude Code CLI is logged in
with** — i.e. the user's own Claude subscription via `claude` login. No
`ANTHROPIC_API_KEY` is required for the default local flow.

> **ToS note.** Anthropic does not permit third parties to *offer claude.ai
> login* to *their* end users. Stockquare is a **personal, local-first** tool:
> each user installs and logs into **their own** Claude Code. The deployment
> guide must state this prerequisite explicitly. `ANTHROPIC_API_KEY` (or a
> Bedrock/Vertex/Foundry provider) remains supported as an override for users
> who prefer API-key billing.

### 5.2 Tool surface lockdown (security-critical)

Because the agent runs on the user's machine through Claude Code, the built-in
tools (Bash, Read, Write, Edit, WebFetch, WebSearch, Glob, Grep, …) would grant
the model shell/filesystem access. They are removed:

- `tools=[]` → all built-ins dropped from the model's context.
- `setting_sources=[]` → do **not** load the user's `~/.claude` settings,
  `CLAUDE.md`, skills, or project rules into this agent.
- `allowed_tools` lists only the **read** MCP tools; the mutate tools
  (`add_to_watchlist` / `remove_from_watchlist`) are gated by `can_use_tool`;
  everything else falls through to a deny.
- `permission_mode="default"` (never `bypassPermissions` / `acceptEdits`).

### Settings (`app/config.py`)

| Setting | Env | Default | Notes |
|---------|-----|---------|-------|
| `assistant_enabled` | `ASSISTANT_ENABLED` | `true` | Global kill switch for the feature. |
| `assistant_model` | `ASSISTANT_MODEL` | `haiku` | Model alias passed to the SDK. |
| `assistant_max_turns` | `ASSISTANT_MAX_TURNS` | `5` | SDK `max_turns` — tool-loop round-trip cap. |
| `assistant_max_budget_usd` | `ASSISTANT_MAX_BUDGET_USD` | `null` | Optional SDK `max_budget_usd` per turn. |
| `assistant_cli_path` | `ASSISTANT_CLI_PATH` | `null` | Override path to the `claude` executable (else SDK auto-discovers). |

Readiness is determined at runtime by whether the Claude Code CLI is present and
authenticated (a startup/health probe), **not** by an API key. If unavailable,
assistant endpoints return 503 `ASSISTANT_NOT_CONFIGURED`; the rest of the app
is unaffected (same tolerance as KIS creds).

## 6. Error Handling

| Scenario | HTTP | Code |
|----------|------|------|
| `assistant_enabled=false` / Claude Code CLI missing or not logged in | 503 | `ASSISTANT_NOT_CONFIGURED` |
| Request validation (empty / too many messages) | 422 | — |
| SDK / Claude Code failure, timeout, or budget abort | 502 | `ASSISTANT_API_ERROR` |
| Tool-loop budget exceeded (max_turns) | 200 | — (partial `reply`, note appended) |
| Confirm a non-mutate / unknown tool | 400 | `INVALID_ACTION` |
| Individual tool execution failed | 200 | — (recorded in `tool_calls[].ok=false` with `error_code`) |
| KIS-dependent tool with creds missing | 200 | — (`tool_calls[].error_code = KIS_NOT_CONFIGURED`) |

The chat endpoint degrades gracefully: a single failed tool never 500s the whole
turn — its handler returns `is_error: True`, becoming a failed `ToolCallResult`
the model can narrate around. New exceptions: `AssistantNotConfiguredError`
(503 / `ASSISTANT_NOT_CONFIGURED`), `AssistantAPIError`
(502 / `ASSISTANT_API_ERROR`) in `app/core/exceptions.py`.

## 7. Data Model

Phase 1 is **stateless** — no conversation persistence. The client owns history
and replays it each turn. (Phase 2 may persist conversations / SDK sessions for
audit; see §9.)

## 8. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Assistant endpoints | `app/api/v1/assistant.py` | api |
| Assistant service (SDK orchestration) | `app/services/assistant.py` | services |
| Tool registry: `@tool` defs + MCP server + handlers | `app/services/assistant_tools.py` | services |
| Turn collector + permission gate | `app/services/assistant_tools.py` | services |
| Claude Agent SDK runner wrapper | `app/services/agent_runner.py` | services |
| Stock ranking (new) | `app/services/stocks.py` (`rank_stocks`) + `app/kis/client.py` | services / kis |
| Domain models | `app/models/assistant.py` | models |
| Exceptions | `app/core/exceptions.py` | core |
| Settings | `app/config.py` | core |

`api/` calls `services/assistant.py` only. The assistant service configures the
SDK runner; the tool handlers call the **existing services** (`stocks`,
`watchlist`) — they never call `kis/` or `db/` directly for tool effects
(dependency rule in `PROJECT_STRUCTURE.md`). Router registration in
`app/api/v1/router.py`.

### Testing (GOLDEN_RULE §4)

- Mock the SDK boundary (`query` / `ClaudeSDKClient`) to yield canned
  `AssistantMessage` / `ToolUseBlock` / `ResultMessage` streams — the same
  discipline as mocking KIS responses. No real Claude Code spawn in unit tests.
- Test tool handlers directly: schema re-validation, `is_error` on bad input,
  collector population, and that KIS failures become `is_error` rather than
  raising.
- Test the `can_use_tool` gate: each mutate tool (`add_to_watchlist`,
  `remove_from_watchlist`) is denied and a `PendingAction` is recorded;
  `/confirm` executes the service without the model.
- Test the lockdown config: `tools=[]`, `setting_sources=[]`, read-only
  `allowed_tools`, `permission_mode="default"`.

## 9. Phasing & Extensions

- **Phase 1** — `chat` + `confirm` via the Claude Agent SDK over local Claude
  Code; tools across four domains (lookup / chart / watchlist / portfolio) —
  7 read + 2 mutate; KIS ranking added to `stocks`; `can_use_tool` confirmation
  gate on mutations; built-in tools locked down; no order tool; no persistence;
  single-prompt replay (§4.3a). SSE streaming (`/chat/stream`,
  `text/event-stream`) so tokens render live ships alongside the non-streaming
  `/chat` fallback.
- **Phase 2** — SDK **session resume** (§4.3b) for lower latency; conversation
  persistence + audit log of executed actions.
- **Phase 3** — Register `strategy` tools (create/evaluate a strategy from NL)
  and, behind the existing trading safety gates + an extra confirmation, an
  order-placement tool. Real-money actions inherit `TRADING.md` / `STRATEGY.md`
  gate stacks; the assistant never bypasses them, and order tools are gated by
  `can_use_tool` exactly like `add_to_watchlist`.
