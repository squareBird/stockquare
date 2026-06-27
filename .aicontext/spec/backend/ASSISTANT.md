# Assistant Spec (Backend)

A conversational AI assistant that turns natural-language requests into actions
against the existing Stockquare API. The user types a message (e.g. "등락률
상위 조건으로 추천종목 알려줘", "추천 종목들 관심종목에 추가해줘"); the
assistant reasons over the request, calls **tools** that wrap existing services,
and replies in Korean. The assistant is the *orchestration* layer — it owns no
business logic of its own; every effect goes through an existing service.

> **Safety stance.** Read tools (recommend, search, quote, ranking) run freely.
> **Mutating tools** (watchlist add, …) are never executed inline — the
> assistant *proposes* them and the client must send an explicit confirmation
> turn before they run. Trading/order placement is **out of scope for Phase 1**
> and no order tool is registered.

## 0. Concepts

| Term | Meaning |
|------|---------|
| **Conversation** | An ordered list of `messages` the client sends on every turn (stateless server; the client owns history). |
| **Tool** | A typed capability the model may call. Each tool wraps one existing service method. Tools are `read` or `mutate`. |
| **Tool loop** | Server-side agentic loop: model → tool_use → server runs tool → tool_result → model, until the model returns a final text answer (bounded by `ASSISTANT_MAX_TURNS`). |
| **Proposed action** | A `mutate` tool the model wants to run. It is **not executed**; it is returned to the client as a `pending_action` for confirmation. |
| **Confirmation turn** | A follow-up request carrying the `pending_action` id the user approved; only then does the server execute the mutate tool. |

## 1. Endpoints

All assistant endpoints live under `/api/v1/assistant`.

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
    tool: str
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

### POST /api/v1/assistant/confirm

Executes one approved mutate action. The client echoes back the
`PendingAction` it received (the server is stateless and re-validates the input
against the tool schema before running it).

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
**only** surface the model can affect the system through.

| Tool | Kind | Wraps | Purpose |
|------|------|-------|---------|
| `rank_stocks` | read | `stocks.rank_stocks` (§3 KIS ranking) | Condition-based recommendation: top stocks by fluctuation / volume. |
| `search_stocks` | read | `stocks.search` | Resolve a name/keyword → symbols. |
| `get_quote` | read | `stocks` price lookup (KIS `inquire-price`) | Current price/change for a symbol. |
| `list_watchlist` | read | `watchlist.list_watchlist` | Read the user's current watchlist. |
| `add_to_watchlist` | **mutate** | `watchlist.add_watchlist` (per symbol) | Add one or more symbols to the watchlist. |

`add_to_watchlist` accepts a list but executes per-symbol through the existing
`WatchlistService.add_watchlist`, which already enforces the 20-item cap,
duplicate rejection, and symbol validation. Per-symbol failures are collected
into `result.skipped` with their `error_code`; the partial success still
returns `ok: true`.

### Tool schemas (Anthropic tool-use format)

Tools are declared with JSON Schema `input_schema` and passed to the model via
the Anthropic Messages API `tools` parameter. Example:
```python
RANK_STOCKS_TOOL = {
    "name": "rank_stocks",
    "description": "Return top KRX stocks ranked by a condition. Use for "
                   "recommendation requests like '등락률 상위 종목 추천'.",
    "input_schema": {
        "type": "object",
        "properties": {
            "by": {"type": "string", "enum": ["fluctuation", "volume"]},
            "direction": {"type": "string", "enum": ["up", "down"], "default": "up"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
        },
        "required": ["by"],
    },
}
```

Tool input is validated with a Pydantic model **before** the wrapped service is
called (never trust model output directly). A schema-invalid tool call is
returned to the model as a `tool_result` with `is_error: true` so it can retry.

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
`KISAPIError` / `KISNotConfiguredError` — the tool wrapper converts it to a
failed `ToolCallResult` rather than letting it abort the whole chat.

## 4. Agentic Loop

```
1. Build system prompt (static, prompt-cached) + tools + messages.
2. Call Anthropic Messages API.
3. If stop_reason == "tool_use":
     for each tool_use block:
       - read tool   → validate input, run service, append tool_result
       - mutate tool → DO NOT run; record a PendingAction, append a
                       tool_result telling the model it is "awaiting user
                       confirmation" so it stops asking to run it again
     loop back to step 2 (bounded by ASSISTANT_MAX_TURNS, default 5)
4. stop_reason == "end_turn" → return final text as `reply`.
```

- The loop budget (`ASSISTANT_MAX_TURNS`) bounds tool round-trips; exceeding it
  returns the best partial answer with a note.
- Recommendations surfaced by `rank_stocks` / `search_stocks` are collected into
  `recommendations[]` so the client can render them as cards (and offer "add to
  watchlist") independent of the prose `reply`.
- The system prompt instructs the model: answer in Korean; never claim a
  mutation succeeded — propose it; cite symbols by code+name.

## 5. Anthropic Integration

- SDK: `anthropic` (async client). Shared with `STRATEGY.md` §10 (`strategy_ai`).
- Default model: `claude-haiku-4-5-20251001` (fast/cheap for tool routing);
  configurable via `ASSISTANT_MODEL`. Heavier reasoning can opt into a larger
  model later.
- **Prompt caching** applied to the static system prompt + tool definitions
  (`cache_control`) to cut cost across turns.
- Structured/tool output only — no free-text scraping of the model's prose for
  actions.

### Settings (`app/core/config.py`)

| Setting | Env | Default | Notes |
|---------|-----|---------|-------|
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | `""` | Missing → assistant endpoints return 503 `ASSISTANT_NOT_CONFIGURED`; rest of app unaffected (same tolerance as KIS creds). |
| `assistant_model` | `ASSISTANT_MODEL` | `claude-haiku-4-5-20251001` | |
| `assistant_max_turns` | `ASSISTANT_MAX_TURNS` | `5` | Tool-loop round-trip cap. |
| `assistant_enabled` | `ASSISTANT_ENABLED` | `true` | Global kill switch for the feature. |

## 6. Error Handling

| Scenario | HTTP | Code |
|----------|------|------|
| `ANTHROPIC_API_KEY` missing / `assistant_enabled=false` | 503 | `ASSISTANT_NOT_CONFIGURED` |
| Request validation (empty / too many messages) | 422 | — |
| Anthropic API failure or timeout | 502 | `ASSISTANT_API_ERROR` |
| Tool-loop budget exceeded | 200 | — (partial `reply`, note appended) |
| Confirm a non-mutate / unknown tool | 400 | `INVALID_ACTION` |
| Individual tool execution failed | 200 | — (recorded in `tool_calls[].ok=false` with `error_code`) |
| KIS-dependent tool with creds missing | 200 | — (`tool_calls[].error_code = KIS_NOT_CONFIGURED`) |

The chat endpoint degrades gracefully: a single failed tool never 500s the whole
turn — it becomes a failed `ToolCallResult` the model can narrate around.
New exception: `AssistantNotConfiguredError` (503 / `ASSISTANT_NOT_CONFIGURED`),
`AssistantAPIError` (502 / `ASSISTANT_API_ERROR`) in `app/core/exceptions.py`.

## 7. Data Model

Phase 1 is **stateless** — no conversation persistence. The client owns history
and replays it each turn. (Phase 2 may persist conversations for audit; see §9.)

## 8. Module Mapping

| Component | File | Layer |
|-----------|------|-------|
| Assistant endpoints | `app/api/v1/assistant.py` | api |
| Assistant service (agentic loop) | `app/services/assistant.py` | services |
| Tool registry + schemas + wrappers | `app/services/assistant_tools.py` | services |
| Anthropic client wrapper | `app/services/anthropic_client.py` | services |
| Stock ranking (new) | `app/services/stocks.py` (`rank_stocks`) + `app/kis/client.py` | services / kis |
| Domain models | `app/models/assistant.py` | models |
| Exceptions | `app/core/exceptions.py` | core |
| Settings | `app/core/config.py` | core |

`api/` calls `services/assistant.py` only. The assistant service orchestrates
the tool registry, which calls the **existing services** (`stocks`,
`watchlist`) — it never calls `kis/` or `db/` directly for tool effects
(dependency rule in `PROJECT_STRUCTURE.md`). Router registration in
`app/api/v1/router.py`.

## 9. Phasing & Extensions

- **Phase 1** — Non-streaming `chat` + `confirm`, 5 read/mutate tools above,
  KIS ranking added to `stocks`, confirmation gate on mutations, no order tool,
  no persistence.
- **Phase 2** — SSE streaming (`text/event-stream`) so tokens render live;
  conversation persistence + audit log of executed actions.
- **Phase 3** — Register `strategy` tools (create/evaluate a strategy from NL)
  and, behind the existing trading safety gates + an extra confirmation, an
  order-placement tool. Real-money actions inherit `TRADING.md` / `STRATEGY.md`
  gate stacks; the assistant never bypasses them.
