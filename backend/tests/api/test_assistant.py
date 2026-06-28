"""Tests for /api/v1/assistant endpoints.

The Claude Agent SDK boundary (`agent_runner.run_agent`) is mocked so no local
Claude Code is spawned — the same discipline as mocking KIS. To simulate the
model calling tools, the test wraps `build_tool_context` to capture the
per-request ToolContext, then the fake runner drives the real handlers / gate
through it — so collector population (recommendations, pending actions) is
exercised end-to-end.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import AssistantAPIError
from app.kis.master import StockMasterRow
from app.kis.models import RankingResponse, RankingRow, StockPriceOutput, StockPriceResponse
from app.models.stocks import StockMarket
from app.services.assistant import runner as agent_runner
from app.services.assistant import service as assistant_module
from app.services.assistant.tools import (
    ADD_TO_WATCHLIST,
    RANK_STOCKS,
    ToolContext,
    build_tool_context,
    qualified_name,
)
from app.services.stock_index import StockMasterIndex
from tests.conftest import FakeKISClient


@pytest.fixture(autouse=True)
def _claude_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the local Claude Code CLI is installed for every test here."""
    monkeypatch.setattr(agent_runner, "claude_code_available", lambda settings: True)


@pytest.fixture
def captured_ctx(monkeypatch: pytest.MonkeyPatch) -> list[ToolContext]:
    """Capture the ToolContext the service builds for each chat turn."""
    captured: list[ToolContext] = []

    def _wrapped(**kwargs):
        ctx = build_tool_context(**kwargs)
        captured.append(ctx)
        return ctx

    monkeypatch.setattr(assistant_module, "build_tool_context", _wrapped)
    return captured


def _seed_index(index: StockMasterIndex, *rows: tuple[str, str]) -> None:
    index.replace(
        [StockMasterRow(symbol=s, name_ko=n, name_en="", market=StockMarket.KOSPI) for s, n in rows]
    )


@pytest.mark.asyncio
async def test_chat_recommends_via_rank_tool(
    app_client: AsyncClient,
    fake_kis_client: FakeKISClient,
    stock_index: StockMasterIndex,
    captured_ctx: list[ToolContext],
    monkeypatch,
) -> None:
    _seed_index(stock_index, ("005930", "삼성전자"))
    fake_kis_client.ranking_fluctuation.return_value = RankingResponse(
        rt_cd="0",
        output=[RankingRow(stck_shrn_iscd="005930", stck_prpr="72000", prdy_ctrt="5.1", acml_vol="100")],
    )

    async def fake_run(prompt, options):
        # Simulate the model calling rank_stocks during the loop.
        await captured_ctx[-1].handlers[RANK_STOCKS]({"by": "fluctuation", "limit": 5})
        return "등락률 상위 종목입니다: 삼성전자(005930)."

    monkeypatch.setattr(agent_runner, "run_agent", fake_run)

    resp = await app_client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "등락률 상위 추천"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "삼성전자" in body["reply"]
    assert body["recommendations"][0]["symbol"] == "005930"
    assert body["recommendations"][0]["name"] == "삼성전자"
    assert body["tool_calls"][0]["tool"] == RANK_STOCKS
    assert body["pending_actions"] == []


@pytest.mark.asyncio
async def test_chat_proposes_mutation_without_executing(
    app_client: AsyncClient,
    fake_kis_client: FakeKISClient,
    captured_ctx: list[ToolContext],
    monkeypatch,
) -> None:
    async def fake_run(prompt, options):
        # Model attempts add_to_watchlist → gate denies + records pending action.
        await captured_ctx[-1].can_use_tool(
            qualified_name(ADD_TO_WATCHLIST), {"symbols": ["005930"]}, None
        )
        return "삼성전자(005930)를 관심종목에 추가할까요?"

    monkeypatch.setattr(agent_runner, "run_agent", fake_run)

    resp = await app_client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "삼성전자 관심종목 추가"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["pending_actions"]) == 1
    assert body["pending_actions"][0]["tool"] == ADD_TO_WATCHLIST
    assert body["pending_actions"][0]["input"] == {"symbols": ["005930"]}
    fake_kis_client.inquire_stock_price.assert_not_called()


@pytest.mark.asyncio
async def test_confirm_executes_mutation(
    app_client: AsyncClient, fake_kis_client: FakeKISClient, stock_index: StockMasterIndex
) -> None:
    _seed_index(stock_index, ("005930", "삼성전자"))
    fake_kis_client.inquire_stock_price.return_value = StockPriceResponse(
        rt_cd="0", output=StockPriceOutput(stck_shrn_iscd="005930", stck_prpr="72000")
    )

    resp = await app_client.post(
        "/api/v1/assistant/confirm",
        json={
            "action": {
                "id": "act_1",
                "tool": "add_to_watchlist",
                "summary": "관심종목에 1종목 추가: 005930",
                "input": {"symbols": ["005930"]},
            }
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["result"]["added"] == ["005930"]

    listing = await app_client.get("/api/v1/watchlist")
    assert listing.json()["count"] == 1


@pytest.mark.asyncio
async def test_confirm_rejects_non_mutate_tool(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/api/v1/assistant/confirm",
        json={"action": {"id": "act_1", "tool": "rank_stocks", "summary": "x", "input": {}}},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_ACTION"


@pytest.mark.asyncio
async def test_chat_502_on_sdk_failure(app_client: AsyncClient, monkeypatch) -> None:
    async def boom(prompt, options):
        raise AssistantAPIError("claude code crashed")

    monkeypatch.setattr(agent_runner, "run_agent", boom)
    resp = await app_client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "안녕"}]},
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "ASSISTANT_API_ERROR"


@pytest.mark.asyncio
async def test_chat_503_when_claude_code_unavailable(app_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(agent_runner, "claude_code_available", lambda settings: False)
    resp = await app_client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "안녕"}]},
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "ASSISTANT_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_chat_validation_rejects_empty_messages(app_client: AsyncClient) -> None:
    resp = await app_client.post("/api/v1/assistant/chat", json={"messages": []})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Streaming endpoint (/chat/stream — Server-Sent Events)
# ---------------------------------------------------------------------------


def _parse_sse(body: str) -> list[dict]:
    """Parse `data: <json>` SSE lines into the list of event dicts."""
    import json

    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


@pytest.mark.asyncio
async def test_chat_stream_emits_deltas_then_final(
    app_client: AsyncClient,
    fake_kis_client: FakeKISClient,
    stock_index: StockMasterIndex,
    captured_ctx: list[ToolContext],
    monkeypatch,
) -> None:
    _seed_index(stock_index, ("005930", "삼성전자"))
    fake_kis_client.ranking_fluctuation.return_value = RankingResponse(
        rt_cd="0",
        output=[RankingRow(stck_shrn_iscd="005930", stck_prpr="72000", prdy_ctrt="5.1", acml_vol="100")],
    )

    async def fake_stream(prompt, options):
        await captured_ctx[-1].handlers[RANK_STOCKS]({"by": "fluctuation", "limit": 5})
        yield {"type": "delta", "text": "삼성전자"}
        yield {"type": "delta", "text": "(005930) 추천합니다."}
        yield {"type": "result", "text": "삼성전자(005930) 추천합니다."}

    monkeypatch.setattr(agent_runner, "run_agent_stream", fake_stream)

    resp = await app_client.post(
        "/api/v1/assistant/chat/stream",
        json={"messages": [{"role": "user", "content": "등락률 상위 추천"}]},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    deltas = [e["text"] for e in events if e["type"] == "delta"]
    assert deltas == ["삼성전자", "(005930) 추천합니다."]

    final = next(e for e in events if e["type"] == "final")
    assert final["reply"] == "삼성전자(005930) 추천합니다."
    assert final["recommendations"][0]["symbol"] == "005930"
    assert final["tool_calls"][0]["tool"] == RANK_STOCKS
    assert final["pending_actions"] == []


@pytest.mark.asyncio
async def test_chat_stream_surfaces_pending_action_in_final(
    app_client: AsyncClient,
    fake_kis_client: FakeKISClient,
    captured_ctx: list[ToolContext],
    monkeypatch,
) -> None:
    async def fake_stream(prompt, options):
        await captured_ctx[-1].can_use_tool(
            qualified_name(ADD_TO_WATCHLIST), {"symbols": ["005930"]}, None
        )
        yield {"type": "delta", "text": "추가할까요?"}
        yield {"type": "result", "text": "삼성전자(005930)를 관심종목에 추가할까요?"}

    monkeypatch.setattr(agent_runner, "run_agent_stream", fake_stream)

    resp = await app_client.post(
        "/api/v1/assistant/chat/stream",
        json={"messages": [{"role": "user", "content": "삼성전자 관심종목 추가"}]},
    )
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    final = next(e for e in events if e["type"] == "final")
    assert len(final["pending_actions"]) == 1
    assert final["pending_actions"][0]["tool"] == ADD_TO_WATCHLIST
    assert final["pending_actions"][0]["input"] == {"symbols": ["005930"]}
    fake_kis_client.inquire_stock_price.assert_not_called()


@pytest.mark.asyncio
async def test_chat_stream_emits_error_event_on_sdk_failure(
    app_client: AsyncClient, monkeypatch
) -> None:
    async def boom(prompt, options):
        raise AssistantAPIError("claude code crashed")
        yield  # pragma: no cover — make this an async generator

    monkeypatch.setattr(agent_runner, "run_agent_stream", boom)
    resp = await app_client.post(
        "/api/v1/assistant/chat/stream",
        json={"messages": [{"role": "user", "content": "안녕"}]},
    )
    # The body opened OK; the failure surfaces as an in-stream error event.
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "error"
    assert "final" not in {e["type"] for e in events}


@pytest.mark.asyncio
async def test_chat_stream_503_when_claude_code_unavailable(
    app_client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(agent_runner, "claude_code_available", lambda settings: False)
    resp = await app_client.post(
        "/api/v1/assistant/chat/stream",
        json={"messages": [{"role": "user", "content": "안녕"}]},
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "ASSISTANT_NOT_CONFIGURED"
