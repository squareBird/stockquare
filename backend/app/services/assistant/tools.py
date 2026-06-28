"""Assistant tool registry — in-process MCP tools over existing services.

The assistant (`app/services/assistant.py`) drives the Claude Agent SDK; the
model can only affect the system through the tools defined here. Each tool
wraps exactly one existing service call. Read tools run inline; the single
mutate tool (`add_to_watchlist`) is gated by `can_use_tool` (§4.1 of
`ASSISTANT.md`) and surfaced as a `PendingAction` instead of executing.

The SDK's `@tool` decorator forwards only `content` / `is_error` from a handler
return (it drops `structuredContent`), so structured results — recommendations,
per-call status — are pushed into a request-scoped :class:`TurnCollector` that
the service reads after the agent loop.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from claude_agent_sdk import (
    PermissionResultAllow,
    PermissionResultDeny,
    ToolAnnotations,
    ToolPermissionContext,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import McpSdkServerConfig
from pydantic import BaseModel, Field, ValidationError

from app.core.exceptions import StockquareError
from app.models.assistant import (
    PendingAction,
    Recommendation,
    ToolCallResult,
    ViewAction,
)
from app.models.stocks import ChartInterval, RankBy, RankDirection, RankedStock
from app.services.portfolio import PortfolioHoldingsService, PortfolioService
from app.services.stocks import StockSearchItem, StocksService
from app.services.watchlist import WatchlistService

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "stockquare"

# Bare tool names (wire contract). The SDK namespaces them as
# `mcp__stockquare__<name>` (see `qualified_name`). Tools are grouped by domain
# so the model — and anyone reading this — can reason about capabilities by
# area: lookup / chart / watchlist / portfolio.

# -- Lookup & ranking (read) --
RANK_STOCKS = "rank_stocks"
SEARCH_STOCKS = "search_stocks"
GET_QUOTE = "get_quote"
# -- Chart (read) --
GET_CHART = "get_chart"
# -- Watchlist (read + mutate) --
LIST_WATCHLIST = "list_watchlist"
ADD_TO_WATCHLIST = "add_to_watchlist"
REMOVE_FROM_WATCHLIST = "remove_from_watchlist"
# -- Portfolio (read) --
GET_ACCOUNT_SUMMARY = "get_account_summary"
LIST_HOLDINGS = "list_holdings"

# Tool groups by domain. READ_TOOLS are pre-approved (allowed_tools); MUTATE
# tools route through the can_use_tool gate and surface as PendingActions.
LOOKUP_TOOLS = (RANK_STOCKS, SEARCH_STOCKS, GET_QUOTE)
CHART_TOOLS = (GET_CHART,)
WATCHLIST_READ_TOOLS = (LIST_WATCHLIST,)
PORTFOLIO_TOOLS = (GET_ACCOUNT_SUMMARY, LIST_HOLDINGS)

READ_TOOLS = (*LOOKUP_TOOLS, *CHART_TOOLS, *WATCHLIST_READ_TOOLS, *PORTFOLIO_TOOLS)
MUTATE_TOOLS = (ADD_TO_WATCHLIST, REMOVE_FROM_WATCHLIST)


def qualified_name(bare: str) -> str:
    """Return the SDK-namespaced tool name for a bare tool name."""
    return f"mcp__{MCP_SERVER_NAME}__{bare}"


# ---------------------------------------------------------------------------
# Tool argument models (re-validate model output before touching a service)
# ---------------------------------------------------------------------------


class RankStocksArgs(BaseModel):
    by: RankBy
    direction: RankDirection = RankDirection.UP
    limit: int = Field(default=5, ge=1, le=20)


class SearchStocksArgs(BaseModel):
    query: str = Field(min_length=1, max_length=40)
    limit: int = Field(default=5, ge=1, le=20)


class GetQuoteArgs(BaseModel):
    symbol: str = Field(pattern=r"^\d{6}$")


class GetChartArgs(BaseModel):
    symbol: str = Field(pattern=r"^\d{6}$")
    interval: ChartInterval = ChartInterval.DAY


class AddToWatchlistArgs(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=20)


class RemoveFromWatchlistArgs(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=20)


# ---------------------------------------------------------------------------
# Request-scoped collector
# ---------------------------------------------------------------------------


@dataclass
class TurnCollector:
    """Accumulates structured results a single chat turn produced."""

    tool_calls: list[ToolCallResult] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    pending_actions: list[PendingAction] = field(default_factory=list)
    view_actions: list[ViewAction] = field(default_factory=list)
    _pending_seq: int = 0

    def record_call(self, tool: str, args: dict, *, ok: bool, error_code: str | None = None) -> None:
        self.tool_calls.append(ToolCallResult(tool=tool, input=args, ok=ok, error_code=error_code))

    def add_recommendations(self, recs: list[Recommendation]) -> None:
        seen = {(r.symbol) for r in self.recommendations}
        for rec in recs:
            if rec.symbol not in seen:
                self.recommendations.append(rec)
                seen.add(rec.symbol)

    def add_view_action(self, *, type: str, params: dict) -> ViewAction:
        action = ViewAction(type=type, params=params)
        self.view_actions.append(action)
        return action

    def add_pending_action(self, *, tool: str, summary: str, action_input: dict) -> PendingAction:
        self._pending_seq += 1
        action = PendingAction(
            id=f"act_{self._pending_seq}",
            tool=tool,
            summary=summary,
            input=action_input,
        )
        self.pending_actions.append(action)
        return action


# ---------------------------------------------------------------------------
# Tool context — MCP server + permission gate bound to one request's services
# ---------------------------------------------------------------------------


ToolHandler = Callable[[dict], Awaitable[dict]]


@dataclass
class ToolContext:
    """Per-request bundle: the MCP server config and the mutate gate.

    `handlers` exposes the bare-name → handler map so tests (and any
    direct-invocation path) can exercise the real handler logic without going
    through the MCP protocol layer.
    """

    server: McpSdkServerConfig
    can_use_tool: object  # CanUseTool callback
    allowed_tool_names: list[str]
    handlers: dict[str, ToolHandler]


def _text(payload: str) -> dict:
    return {"content": [{"type": "text", "text": payload}]}


def _error(payload: str) -> dict:
    return {"content": [{"type": "text", "text": payload}], "is_error": True}


def _summarize_candles(candles: list) -> dict:
    """Reduce an OHLCV series to a compact trend summary for the model.

    Returns first/last close, period return %, period high/low, and a coarse
    trend label — enough for a 1-2 sentence comment, without the full series
    (which the model would otherwise be tempted to dump as a table).
    """
    if not candles:
        return {"available": False}
    first_close = candles[0].close
    last_close = candles[-1].close
    high = max(c.high for c in candles)
    low = min(c.low for c in candles)
    change_pct = round((last_close - first_close) / first_close * 100, 2) if first_close else 0.0
    if change_pct >= 1:
        trend = "up"
    elif change_pct <= -1:
        trend = "down"
    else:
        trend = "flat"
    return {
        "available": True,
        "candle_count": len(candles),
        "first_close": first_close,
        "last_close": last_close,
        "period_high": high,
        "period_low": low,
        "change_pct": change_pct,
        "trend": trend,
    }


def _ranked_to_recommendation(stock: RankedStock, reason: str) -> Recommendation:
    return Recommendation(
        symbol=stock.symbol,
        name=stock.name,
        price=stock.price,
        change_rate=stock.change_rate,
        reason=reason,
    )


def _search_to_recommendation(item: StockSearchItem) -> Recommendation:
    return Recommendation(symbol=item.symbol, name=item.name, reason="검색 결과")


def build_tool_context(
    *,
    stocks: StocksService,
    watchlist: WatchlistService,
    portfolio: PortfolioService,
    holdings: PortfolioHoldingsService,
    collector: TurnCollector,
) -> ToolContext:
    """Build the in-process MCP server and mutate gate for one chat turn.

    Handlers are closures over the request-scoped services + collector, so no
    global state leaks between concurrent requests. Read handlers never raise:
    a service error becomes an ``is_error`` tool result the model narrates
    around, mirroring the watchlist degraded-read pattern.

    Tools are grouped by domain below: lookup/ranking, chart, watchlist
    (read + gated mutates), and portfolio.
    """

    @tool(
        RANK_STOCKS,
        "Return top KRX stocks ranked by a market condition. Use for "
        "recommendation requests like '등락률 상위 종목 추천' or '거래량 많은 종목'.",
        {
            "type": "object",
            "properties": {
                "by": {"type": "string", "enum": ["fluctuation", "volume"]},
                "direction": {"type": "string", "enum": ["up", "down"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["by"],
        },
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def rank_stocks_tool(args: dict) -> dict:
        try:
            parsed = RankStocksArgs(**args)
        except ValidationError as exc:
            return _error(f"Invalid arguments: {exc.errors()}")
        try:
            ranked = await stocks.rank_stocks(
                by=parsed.by,
                direction=parsed.direction,
                limit=parsed.limit,
            )
        except StockquareError as exc:
            collector.record_call(RANK_STOCKS, args, ok=False, error_code=exc.code)
            return _error(f"Ranking failed: {exc.message}")
        reason = "등락률 상위" if parsed.by == RankBy.FLUCTUATION else "거래량 상위"
        collector.add_recommendations([_ranked_to_recommendation(s, reason) for s in ranked])
        collector.record_call(RANK_STOCKS, args, ok=True)
        return _text(json.dumps([s.model_dump() for s in ranked], ensure_ascii=False))

    @tool(
        SEARCH_STOCKS,
        "Resolve a stock name or keyword to candidate symbols. Use to turn a "
        "company name in the user's message into a 6-digit code.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def search_stocks_tool(args: dict) -> dict:
        try:
            parsed = SearchStocksArgs(**args)
        except ValidationError as exc:
            return _error(f"Invalid arguments: {exc.errors()}")
        try:
            items = await stocks.search_stocks(parsed.query, parsed.limit)
        except StockquareError as exc:
            collector.record_call(SEARCH_STOCKS, args, ok=False, error_code=exc.code)
            return _error(f"Search failed: {exc.message}")
        collector.add_recommendations([_search_to_recommendation(i) for i in items])
        collector.record_call(SEARCH_STOCKS, args, ok=True)
        payload = [{"symbol": i.symbol, "name": i.name, "market": i.market} for i in items]
        return _text(json.dumps(payload, ensure_ascii=False))

    @tool(
        GET_QUOTE,
        "Get the current price and daily change for a single 6-digit KRX symbol.",
        {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_quote_tool(args: dict) -> dict:
        try:
            parsed = GetQuoteArgs(**args)
        except ValidationError as exc:
            return _error(f"Invalid arguments: {exc.errors()}")
        try:
            quote = await stocks.get_quote(parsed.symbol)
        except StockquareError as exc:
            collector.record_call(GET_QUOTE, args, ok=False, error_code=exc.code)
            return _error(f"Quote failed: {exc.message}")
        collector.record_call(GET_QUOTE, args, ok=True)
        payload = {
            "symbol": quote.symbol,
            "name": quote.name,
            "price": quote.price,
            "change_rate": quote.change_rate,
            "volume": quote.volume,
        }
        return _text(json.dumps(payload, ensure_ascii=False))

    # --- Chart domain -----------------------------------------------------

    @tool(
        GET_CHART,
        "Display a stock's price chart to the user. Call this whenever the user "
        "asks to SEE/SHOW a chart (e.g. '삼성전자 차트 보여줘'). The chart is "
        "rendered visually in the Trading tab — you do NOT need to draw it. This "
        "returns only summary statistics (period return, high/low, trend); use "
        "them to write a SHORT 1-2 sentence Korean comment about the trend. "
        "NEVER reproduce the candle data as a table or list. The candle "
        "granularity defaults to day (일봉); pass interval=min for 분봉, "
        "week for 주봉, month for 월봉 only when the user explicitly asks for it.",
        {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "interval": {"type": "string", "enum": ["min", "day", "week", "month"]},
            },
            "required": ["symbol"],
        },
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_chart_tool(args: dict) -> dict:
        try:
            parsed = GetChartArgs(**args)
        except ValidationError as exc:
            return _error(f"Invalid arguments: {exc.errors()}")
        try:
            candles = await stocks.get_history(parsed.symbol, parsed.interval)
        except StockquareError as exc:
            collector.record_call(GET_CHART, args, ok=False, error_code=exc.code)
            return _error(f"Chart failed: {exc.message}")
        collector.record_call(GET_CHART, args, ok=True)

        name = stocks.resolve_name(parsed.symbol)
        # Tell the client to open the chart in the Trading tab. The visual chart
        # is the deliverable; the model only adds a short spoken comment.
        collector.add_view_action(
            type="open_chart",
            params={"symbol": parsed.symbol, "name": name, "interval": parsed.interval.value},
        )

        # Hand the model only a compact trend summary — never the full candle
        # series — so it can't (and needn't) redraw the chart as a text table.
        summary = _summarize_candles(candles)
        payload = {
            "symbol": parsed.symbol,
            "name": name,
            "interval": parsed.interval.value,
            **summary,
        }
        return _text(json.dumps(payload, ensure_ascii=False))

    # --- Watchlist domain -------------------------------------------------

    @tool(
        LIST_WATCHLIST,
        "List the symbols currently in the user's watchlist.",
        {"type": "object", "properties": {}},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_watchlist_tool(args: dict) -> dict:
        try:
            result = await watchlist.list_watchlist()
        except StockquareError as exc:
            collector.record_call(LIST_WATCHLIST, args, ok=False, error_code=exc.code)
            return _error(f"Watchlist read failed: {exc.message}")
        collector.record_call(LIST_WATCHLIST, args, ok=True)
        payload = [{"symbol": i.symbol, "name": i.name, "price": i.price} for i in result.items]
        payload += [{"symbol": e.symbol, "error": e.error_code} for e in result.errors]
        return _text(json.dumps(payload, ensure_ascii=False))

    @tool(
        ADD_TO_WATCHLIST,
        "Add one or more 6-digit KRX symbols to the user's watchlist. This is "
        "a mutation: it requires explicit user confirmation and is never run "
        "directly — propose it and ask the user to confirm.",
        {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["symbols"],
        },
    )
    async def add_to_watchlist_tool(args: dict) -> dict:
        # Never reached: the gate denies this tool before execution. Present so
        # the model sees a callable mutate tool. If the SDK ever routed past the
        # gate, fail closed rather than mutate.
        return _error("add_to_watchlist must be confirmed by the user; not executed.")

    @tool(
        REMOVE_FROM_WATCHLIST,
        "Remove one or more 6-digit KRX symbols from the user's watchlist. This "
        "is a mutation: it requires explicit user confirmation and is never run "
        "directly — propose it and ask the user to confirm.",
        {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["symbols"],
        },
    )
    async def remove_from_watchlist_tool(args: dict) -> dict:
        # Never reached: gated like add_to_watchlist. Fail closed if routed past.
        return _error("remove_from_watchlist must be confirmed by the user; not executed.")

    # --- Portfolio domain -------------------------------------------------

    @tool(
        GET_ACCOUNT_SUMMARY,
        "Get the user's account summary: total asset, daily profit, cash "
        "balance, and holdings count. Use for '내 계좌', '총자산', '수익' 류 질문.",
        {"type": "object", "properties": {}},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def get_account_summary_tool(args: dict) -> dict:
        try:
            summary = await portfolio.get_account_summary()
        except StockquareError as exc:
            collector.record_call(GET_ACCOUNT_SUMMARY, args, ok=False, error_code=exc.code)
            return _error(f"Account summary failed: {exc.message}")
        collector.record_call(GET_ACCOUNT_SUMMARY, args, ok=True)
        payload = {
            "total_asset": summary.total_asset,
            "total_profit": summary.total_profit,
            "total_profit_rate": summary.total_profit_rate,
            "daily_profit": summary.daily_profit,
            "daily_profit_rate": summary.daily_profit_rate,
            "cash_balance": summary.cash_balance,
            "holdings_count": summary.holdings_count,
            "errors": [e.field for e in summary.errors],
        }
        return _text(json.dumps(payload, ensure_ascii=False))

    @tool(
        LIST_HOLDINGS,
        "List the user's current stock holdings with quantity, average price, "
        "current price, and profit. Use for '내 보유 종목', '내 주식' 류 질문.",
        {"type": "object", "properties": {}},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def list_holdings_tool(args: dict) -> dict:
        try:
            result = await holdings.get_holdings()
        except StockquareError as exc:
            collector.record_call(LIST_HOLDINGS, args, ok=False, error_code=exc.code)
            return _error(f"Holdings read failed: {exc.message}")
        collector.record_call(LIST_HOLDINGS, args, ok=True)
        payload = {
            "holdings": [
                {
                    "symbol": h.symbol,
                    "name": h.name,
                    "quantity": h.quantity,
                    "avg_purchase_price": h.avg_purchase_price,
                    "current_price": h.current_price,
                    "profit": h.profit,
                    "profit_rate": h.profit_rate,
                }
                for h in result.holdings
            ],
            "errors": [e.error_code for e in result.errors],
        }
        return _text(json.dumps(payload, ensure_ascii=False))

    server = create_sdk_mcp_server(
        name=MCP_SERVER_NAME,
        version="1.0.0",
        tools=[
            # lookup & ranking
            rank_stocks_tool,
            search_stocks_tool,
            get_quote_tool,
            # chart
            get_chart_tool,
            # watchlist
            list_watchlist_tool,
            add_to_watchlist_tool,
            remove_from_watchlist_tool,
            # portfolio
            get_account_summary_tool,
            list_holdings_tool,
        ],
    )

    async def can_use_tool(
        tool_name: str,
        input: dict,
        context: ToolPermissionContext,
    ) -> PermissionResultAllow | PermissionResultDeny:
        """Gate mutate tools; deny + record a PendingAction (§4.1)."""
        if tool_name == qualified_name(ADD_TO_WATCHLIST):
            try:
                parsed = AddToWatchlistArgs(**input)
            except ValidationError as exc:
                return PermissionResultDeny(message=f"Invalid arguments: {exc.errors()}")
            symbols = parsed.symbols
            collector.add_pending_action(
                tool=ADD_TO_WATCHLIST,
                summary=f"관심종목에 {len(symbols)}종목 추가: {', '.join(symbols)}",
                action_input={"symbols": symbols},
            )
            return PermissionResultDeny(
                message=(
                    "Awaiting explicit user confirmation; do not retry this tool. "
                    "Ask the user to confirm in Korean."
                ),
            )
        if tool_name == qualified_name(REMOVE_FROM_WATCHLIST):
            try:
                parsed_remove = RemoveFromWatchlistArgs(**input)
            except ValidationError as exc:
                return PermissionResultDeny(message=f"Invalid arguments: {exc.errors()}")
            symbols = parsed_remove.symbols
            collector.add_pending_action(
                tool=REMOVE_FROM_WATCHLIST,
                summary=f"관심종목에서 {len(symbols)}종목 삭제: {', '.join(symbols)}",
                action_input={"symbols": symbols},
            )
            return PermissionResultDeny(
                message=(
                    "Awaiting explicit user confirmation; do not retry this tool. "
                    "Ask the user to confirm in Korean."
                ),
            )
        # Read tools are pre-approved via allowed_tools; anything else is denied.
        return PermissionResultDeny(message="Tool not permitted.")

    return ToolContext(
        server=server,
        can_use_tool=can_use_tool,
        allowed_tool_names=[qualified_name(name) for name in READ_TOOLS],
        handlers={
            RANK_STOCKS: rank_stocks_tool.handler,
            SEARCH_STOCKS: search_stocks_tool.handler,
            GET_QUOTE: get_quote_tool.handler,
            GET_CHART: get_chart_tool.handler,
            LIST_WATCHLIST: list_watchlist_tool.handler,
            ADD_TO_WATCHLIST: add_to_watchlist_tool.handler,
            REMOVE_FROM_WATCHLIST: remove_from_watchlist_tool.handler,
            GET_ACCOUNT_SUMMARY: get_account_summary_tool.handler,
            LIST_HOLDINGS: list_holdings_tool.handler,
        },
    )


async def execute_mutate_action(action: PendingAction, watchlist: WatchlistService) -> tuple[dict, str]:
    """Execute a confirmed mutate action directly — no model involved.

    Re-validates the echoed input against the tool schema (the server is
    stateless) and runs the wrapped service. Returns ``(result, message)``.
    """
    if action.tool == ADD_TO_WATCHLIST:
        parsed = AddToWatchlistArgs(**action.input)
        added: list[str] = []
        skipped: list[dict] = []
        for symbol in parsed.symbols:
            try:
                await watchlist.add_watchlist(symbol)
                added.append(symbol)
            except StockquareError as exc:
                skipped.append({"symbol": symbol, "error_code": exc.code})
        result = {"added": added, "skipped": skipped}
        if added and not skipped:
            message = f"{len(added)}종목을 관심종목에 추가했습니다."
        elif added:
            message = f"{len(added)}종목을 추가했고 {len(skipped)}종목은 건너뛰었습니다."
        else:
            message = "추가된 종목이 없습니다."
        return result, message

    if action.tool == REMOVE_FROM_WATCHLIST:
        parsed_remove = RemoveFromWatchlistArgs(**action.input)
        removed: list[str] = []
        skipped = []
        for symbol in parsed_remove.symbols:
            try:
                await watchlist.delete_watchlist_by_symbol(symbol)
                removed.append(symbol)
            except StockquareError as exc:
                skipped.append({"symbol": symbol, "error_code": exc.code})
        result = {"removed": removed, "skipped": skipped}
        if removed and not skipped:
            message = f"{len(removed)}종목을 관심종목에서 삭제했습니다."
        elif removed:
            message = f"{len(removed)}종목을 삭제했고 {len(skipped)}종목은 건너뛰었습니다."
        else:
            message = "삭제된 종목이 없습니다."
        return result, message

    # Unknown / non-mutate tools are rejected by the caller before reaching here.
    raise ValueError(f"Not an executable mutate action: {action.tool}")
