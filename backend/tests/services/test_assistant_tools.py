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
from app.services.assistant.tools import (
    ADD_TO_WATCHLIST,
    GET_ACCOUNT_SUMMARY,
    GET_CHART,
    GET_QUOTE,
    LIST_HOLDINGS,
    LIST_WATCHLIST,
    RANK_STOCKS,
    REMOVE_FROM_WATCHLIST,
    SEARCH_STOCKS,
    TurnCollector,
    build_tool_context,
    execute_mutate_action,
    qualified_name,
)
from app.services.stocks import StockSearchItem


def _ctx(stocks=None, watchlist=None, portfolio=None, holdings=None):
    collector = TurnCollector()
    ctx = build_tool_context(
        stocks=stocks or AsyncMock(),
        watchlist=watchlist or AsyncMock(),
        portfolio=portfolio or AsyncMock(),
        holdings=holdings or AsyncMock(),
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


# ---------------------------------------------------------------------------
# Chart domain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chart_tool_emits_view_action_and_summary_not_candles() -> None:
    from unittest.mock import MagicMock

    from app.models.stocks import Candle, ChartInterval

    stocks = AsyncMock()
    stocks.resolve_name = MagicMock(return_value="삼성전자")  # sync method
    stocks.get_history.return_value = [
        Candle(time="2026-06-01", open=70000, high=72000, low=69000, close=70000, volume=1000),
        Candle(time="2026-06-02", open=70000, high=75000, low=69500, close=74000, volume=1200),
    ]
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[GET_CHART]({"symbol": "005930", "interval": "day"})
    payload = json.loads(result["content"][0]["text"])

    stocks.get_history.assert_awaited_once_with("005930", ChartInterval.DAY)
    # The model gets a compact summary, NOT the raw candle series.
    assert "candles" not in payload
    assert payload["symbol"] == "005930"
    assert payload["name"] == "삼성전자"
    assert payload["interval"] == "day"
    assert payload["period_high"] == 75000
    assert payload["period_low"] == 69000
    assert payload["change_pct"] == pytest.approx(5.71, abs=0.01)
    assert payload["trend"] == "up"
    assert collector.tool_calls[0].ok is True
    # A view action tells the client to open the chart in the Trading tab.
    assert len(collector.view_actions) == 1
    action = collector.view_actions[0]
    assert action.type == "open_chart"
    assert action.params == {"symbol": "005930", "name": "삼성전자", "interval": "day"}


@pytest.mark.asyncio
async def test_get_chart_tool_defaults_interval_and_handles_empty_series() -> None:
    from unittest.mock import MagicMock

    from app.models.stocks import ChartInterval

    stocks = AsyncMock()
    stocks.resolve_name = MagicMock(return_value="삼성전자")
    stocks.get_history.return_value = []
    ctx, collector = _ctx(stocks=stocks)

    result = await ctx.handlers[GET_CHART]({"symbol": "005930"})
    payload = json.loads(result["content"][0]["text"])

    stocks.get_history.assert_awaited_once_with("005930", ChartInterval.DAY)
    assert payload["available"] is False
    # Still navigate — the chart view handles the empty/degraded state itself.
    assert collector.view_actions[0].type == "open_chart"


@pytest.mark.asyncio
async def test_get_chart_tool_invalid_symbol_returns_is_error() -> None:
    ctx, collector = _ctx()
    result = await ctx.handlers[GET_CHART]({"symbol": "abc"})
    assert result["is_error"] is True
    assert collector.tool_calls == []


# ---------------------------------------------------------------------------
# Portfolio domain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_account_summary_tool_success() -> None:
    from app.services.portfolio import AccountSummary

    portfolio = AsyncMock()
    portfolio.get_account_summary.return_value = AccountSummary(
        total_asset=1_000_000, daily_profit=5000, cash_balance=200_000, holdings_count=3
    )
    ctx, collector = _ctx(portfolio=portfolio)

    result = await ctx.handlers[GET_ACCOUNT_SUMMARY]({})
    payload = json.loads(result["content"][0]["text"])

    assert payload["total_asset"] == 1_000_000
    assert payload["holdings_count"] == 3
    assert collector.tool_calls[0].ok is True


@pytest.mark.asyncio
async def test_list_holdings_tool_success() -> None:
    from app.services.portfolio import Holding, HoldingsResult

    holdings = AsyncMock()
    holdings.get_holdings.return_value = HoldingsResult(
        holdings=[
            Holding(
                symbol="005930", name="삼성전자", quantity=10, avg_purchase_price=70000,
                current_price=72000, evaluation_amount=720000, purchase_amount=700000,
                profit=20000, profit_rate=2.86,
            )
        ],
        errors=[],
    )
    ctx, collector = _ctx(holdings=holdings)

    result = await ctx.handlers[LIST_HOLDINGS]({})
    payload = json.loads(result["content"][0]["text"])

    assert payload["holdings"][0]["symbol"] == "005930"
    assert payload["holdings"][0]["quantity"] == 10
    assert collector.tool_calls[0].ok is True


# ---------------------------------------------------------------------------
# Watchlist remove (mutate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_gate_denies_and_records_pending_action() -> None:
    ctx, collector = _ctx()

    decision = await ctx.can_use_tool(
        qualified_name(REMOVE_FROM_WATCHLIST),
        {"symbols": ["005930"]},
        None,
    )

    assert decision.behavior == "deny"
    assert len(collector.pending_actions) == 1
    action = collector.pending_actions[0]
    assert action.tool == REMOVE_FROM_WATCHLIST
    assert action.input == {"symbols": ["005930"]}


@pytest.mark.asyncio
async def test_remove_from_watchlist_tool_never_executes_inline() -> None:
    watchlist = AsyncMock()
    ctx, _ = _ctx(watchlist=watchlist)
    result = await ctx.handlers[REMOVE_FROM_WATCHLIST]({"symbols": ["005930"]})
    assert result["is_error"] is True
    watchlist.delete_watchlist_by_symbol.assert_not_called()


@pytest.mark.asyncio
async def test_execute_mutate_action_removes_symbols() -> None:
    watchlist = AsyncMock()
    action = PendingAction(
        id="act_1",
        tool=REMOVE_FROM_WATCHLIST,
        summary="...",
        input={"symbols": ["005930", "000660"]},
    )

    result, message = await execute_mutate_action(action, watchlist)

    assert result == {"removed": ["005930", "000660"], "skipped": []}
    assert "2종목" in message
    assert watchlist.delete_watchlist_by_symbol.await_count == 2


@pytest.mark.asyncio
async def test_execute_mutate_action_remove_partial_failure() -> None:
    from app.core.exceptions import WatchlistNotFoundError

    watchlist = AsyncMock()
    watchlist.delete_watchlist_by_symbol.side_effect = [None, WatchlistNotFoundError("999999")]
    action = PendingAction(
        id="act_1",
        tool=REMOVE_FROM_WATCHLIST,
        summary="...",
        input={"symbols": ["005930", "999999"]},
    )

    result, _ = await execute_mutate_action(action, watchlist)

    assert result["removed"] == ["005930"]
    assert result["skipped"] == [{"symbol": "999999", "error_code": "NOT_FOUND"}]


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
