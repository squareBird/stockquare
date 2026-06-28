"""Tests for the assistant tool registry, mutate gate, and confirm executor.

These exercise the real handler logic directly (via ToolContext.handlers) and
the can_use_tool gate, without spawning Claude Code. See ASSISTANT.md §2/§4.1.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import InvalidSymbolError, KISAPIError
from app.models.assistant import PendingAction
from app.models.stocks import RankedStock
from app.services.assistant_tools import (
    ADD_TO_WATCHLIST,
    GET_QUOTE,
    LIST_WATCHLIST,
    RANK_STOCKS,
    SEARCH_STOCKS,
    TurnCollector,
    build_tool_context,
    execute_mutate_action,
    qualified_name,
)
from app.services.stocks import StockSearchItem


def _ctx(stocks=None, watchlist=None):
    collector = TurnCollector()
    ctx = build_tool_context(
        stocks=stocks or AsyncMock(),
        watchlist=watchlist or AsyncMock(),
        collector=collector,
    )
    return ctx, collector


@pytest.mark.asyncio
async def test_rank_stocks_tool_collects_recommendations() -> None:
    stocks = AsyncMock()
    stocks.rank_stocks.return_value = [
        RankedStock(symbol="005930", name="삼성전자", price=72000, change_rate=5.1, volume=100),
    ]
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[RANK_STOCKS]({"by": "fluctuation", "limit": 5})

    assert "is_error" not in result
    stocks.rank_stocks.assert_awaited_once()
    assert collector.recommendations[0].symbol == "005930"
    assert collector.tool_calls[0].ok is True
    assert collector.tool_calls[0].tool == RANK_STOCKS


@pytest.mark.asyncio
async def test_rank_stocks_tool_bad_args_returns_is_error_not_raise() -> None:
    ctx, collector = _ctx()
    result = await ctx.handlers[RANK_STOCKS]({"by": "not_a_dimension"})
    assert result["is_error"] is True
    # invalid args fail before the service is called → no tool_call recorded
    assert collector.tool_calls == []


@pytest.mark.asyncio
async def test_rank_stocks_tool_kis_failure_becomes_is_error() -> None:
    stocks = AsyncMock()
    stocks.rank_stocks.side_effect = KISAPIError()
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[RANK_STOCKS]({"by": "volume"})

    assert result["is_error"] is True
    assert collector.tool_calls[0].ok is False
    assert collector.tool_calls[0].error_code == "KIS_API_ERROR"


@pytest.mark.asyncio
async def test_search_stocks_tool_collects_results() -> None:
    stocks = AsyncMock()
    stocks.search_stocks.return_value = [
        StockSearchItem(symbol="000660", name="SK하이닉스", market="KOSPI"),
    ]
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[SEARCH_STOCKS]({"query": "하이닉스"})

    assert "is_error" not in result
    assert collector.recommendations[0].symbol == "000660"


@pytest.mark.asyncio
async def test_get_quote_tool_success() -> None:
    stocks = AsyncMock()
    stocks.get_quote.return_value = RankedStock(
        symbol="005930", name="삼성전자", price=72000, change_rate=2.1, volume=10
    )
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[GET_QUOTE]({"symbol": "005930"})
    payload = json.loads(result["content"][0]["text"])

    assert payload["symbol"] == "005930"
    assert payload["price"] == 72000
    assert collector.tool_calls[0].ok is True


@pytest.mark.asyncio
async def test_get_quote_tool_invalid_symbol() -> None:
    stocks = AsyncMock()
    stocks.get_quote.side_effect = InvalidSymbolError("999999")
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[GET_QUOTE]({"symbol": "999999"})

    assert result["is_error"] is True
    assert collector.tool_calls[0].error_code == "INVALID_SYMBOL"


@pytest.mark.asyncio
async def test_mutate_gate_denies_and_records_pending_action() -> None:
    ctx, collector = _ctx()

    decision = await ctx.can_use_tool(
        qualified_name(ADD_TO_WATCHLIST),
        {"symbols": ["005930", "000660"]},
        None,
    )

    assert decision.behavior == "deny"
    assert len(collector.pending_actions) == 1
    action = collector.pending_actions[0]
    assert action.tool == ADD_TO_WATCHLIST
    assert action.input == {"symbols": ["005930", "000660"]}


@pytest.mark.asyncio
async def test_mutate_gate_denies_unknown_tool_without_pending() -> None:
    ctx, collector = _ctx()
    decision = await ctx.can_use_tool("mcp__stockquare__something_else", {}, None)
    assert decision.behavior == "deny"
    assert collector.pending_actions == []


@pytest.mark.asyncio
async def test_add_to_watchlist_tool_never_executes_inline() -> None:
    """Even if the SDK routed past the gate, the handler must fail closed."""
    watchlist = AsyncMock()
    ctx, _ = _ctx(watchlist=watchlist)
    result = await ctx.handlers[ADD_TO_WATCHLIST]({"symbols": ["005930"]})
    assert result["is_error"] is True
    watchlist.add_watchlist.assert_not_called()


@pytest.mark.asyncio
async def test_execute_mutate_action_adds_symbols() -> None:
    watchlist = AsyncMock()
    action = PendingAction(
        id="act_1",
        tool=ADD_TO_WATCHLIST,
        summary="...",
        input={"symbols": ["005930", "000660"]},
    )

    result, message = await execute_mutate_action(action, watchlist)

    assert result == {"added": ["005930", "000660"], "skipped": []}
    assert "2종목" in message
    assert watchlist.add_watchlist.await_count == 2


@pytest.mark.asyncio
async def test_execute_mutate_action_partial_failure() -> None:
    watchlist = AsyncMock()
    watchlist.add_watchlist.side_effect = [None, KISAPIError()]
    action = PendingAction(
        id="act_1",
        tool=ADD_TO_WATCHLIST,
        summary="...",
        input={"symbols": ["005930", "999999"]},
    )

    result, _ = await execute_mutate_action(action, watchlist)

    assert result["added"] == ["005930"]
    assert result["skipped"] == [{"symbol": "999999", "error_code": "KIS_API_ERROR"}]


@pytest.mark.asyncio
async def test_list_watchlist_tool() -> None:
    from datetime import UTC, datetime

    from app.models.watchlist import WatchlistItemResponse
    from app.services.watchlist import WatchlistEnrichmentResult

    watchlist = AsyncMock()
    watchlist.list_watchlist.return_value = WatchlistEnrichmentResult(
        items=[
            WatchlistItemResponse(
                id=1, symbol="005930", name="삼성전자", price=72000, change=100,
                change_rate=1.0, volume=10, sort_order=0, created_at=datetime.now(UTC),
            )
        ],
        errors=[],
    )
    ctx, collector = _ctx(watchlist=watchlist)

    result = await ctx.handlers[LIST_WATCHLIST]({})
    payload = json.loads(result["content"][0]["text"])

    assert payload[0]["symbol"] == "005930"
    assert collector.tool_calls[0].ok is True
