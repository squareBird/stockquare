"""Assistant service — orchestrates the Claude Agent SDK over local Claude Code.

Owns no business logic: it builds the per-request tool context, runs one agent
turn through :mod:`app.services.assistant.runner`, and assembles the response from
the model's text reply plus the request-scoped :class:`TurnCollector`. The
mutate gate denies `add_to_watchlist` inline and surfaces it as a
`PendingAction`; `/confirm` executes it directly without the model.

See `.aicontext/spec/backend/ASSISTANT.md`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.core.exceptions import (
    AssistantAPIError,
    AssistantNotConfiguredError,
    InvalidActionError,
)
from app.models.assistant import (
    ChatMessage,
    ChatResponse,
    ChatRole,
    ConfirmResponse,
    PendingAction,
)
from app.services.assistant import runner as agent_runner
from app.services.assistant.tools import (
    MUTATE_TOOLS,
    TurnCollector,
    build_tool_context,
    execute_mutate_action,
)
from app.services.portfolio import PortfolioHoldingsService, PortfolioService
from app.services.stocks import StocksService
from app.services.watchlist import WatchlistService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "당신은 Stockquare의 한국 주식 투자 보조 AI입니다. "
    "항상 한국어로 간결하게 답하세요. "
    "제공된 Stockquare 도구만 사용하고 그 외 도구는 사용하지 마세요. "
    "종목은 항상 코드와 이름을 함께 언급하세요. "
    "사용할 수 있는 도구는 네 가지 영역입니다: "
    "(1) 조회·추천 — rank_stocks(등락률·거래량 상위), search_stocks(종목 검색), get_quote(현재가); "
    "(2) 차트 — get_chart(차트를 Trading 탭에 표시); "
    "(3) 관심종목 — list_watchlist(목록), add_to_watchlist(추가), remove_from_watchlist(삭제); "
    "(4) 계좌 — get_account_summary(총자산·손익), list_holdings(보유종목). "
    "추천 요청에는 rank_stocks 도구를 사용하세요. "
    "사용자가 차트를 보여달라고 하면 반드시 get_chart 도구를 실제로 호출하세요. "
    "종목 이름만 있으면 먼저 search_stocks로 6자리 코드를 찾은 뒤 그 코드로 get_chart를 "
    "호출하세요. 절대 도구를 호출하지 않고 가격·고저점·등락률을 지어내지 마세요. 그 "
    "수치는 오직 get_chart가 반환한 값만 사용해야 합니다. 차트는 화면에 시각적으로 "
    "표시되므로, 캔들 데이터를 표나 목록으로 나열하지 말고, 도구가 반환한 요약(기간 "
    "등락률·고저점·추세)으로 한두 문장의 짧은 코멘트만 작성하세요. "
    "사용자가 관심종목 추가나 삭제를 요청하면, 망설이지 말고 add_to_watchlist 또는 "
    "remove_from_watchlist 도구를 호출하세요. 시스템이 자동으로 사용자 확인 절차를 "
    "처리하므로, 텍스트로만 '추가할까요?'라고 묻지 말고 반드시 도구를 호출해야 합니다. "
    "변경 작업이 실제로 완료되었다고 절대 단정하지 마세요. "
    "도구가 확인 대기 상태를 반환하면, 사용자에게 확인을 요청하는 짧은 문장으로 답하세요."
)


class AssistantService:
    """Conversational orchestration over existing services."""

    def __init__(
        self,
        *,
        settings: Settings,
        stocks: StocksService,
        watchlist: WatchlistService,
        portfolio: PortfolioService,
        holdings: PortfolioHoldingsService,
    ) -> None:
        self._settings = settings
        self._stocks = stocks
        self._watchlist = watchlist
        self._portfolio = portfolio
        self._holdings = holdings

    def ensure_available(self) -> None:
        """Raise AssistantNotConfiguredError (→ 503) if the assistant can't run.

        Public so the streaming endpoint can pre-flight before opening the SSE
        response body — once the body starts, a raise mid-stream can't map to a
        clean 503 status.
        """
        if not self._settings.assistant_enabled:
            raise AssistantNotConfiguredError("AI assistant is disabled")
        if not agent_runner.claude_code_available(self._settings):
            raise AssistantNotConfiguredError(
                "Local Claude Code not found. Install and log in to use the assistant."
            )

    async def chat(self, messages: list[ChatMessage]) -> ChatResponse:
        """Run one chat turn and return reply + tool activity + pending actions."""
        self.ensure_available()

        collector = TurnCollector()
        ctx = build_tool_context(
            stocks=self._stocks,
            watchlist=self._watchlist,
            portfolio=self._portfolio,
            holdings=self._holdings,
            collector=collector,
        )
        options = agent_runner.build_options(self._settings, ctx, SYSTEM_PROMPT)
        prompt = _serialize_conversation(messages)

        reply = await agent_runner.run_agent(prompt, options)
        if not reply:
            reply = "요청을 처리하지 못했습니다. 다시 시도해 주세요."

        return ChatResponse(
            reply=reply,
            tool_calls=collector.tool_calls,
            pending_actions=collector.pending_actions,
            recommendations=collector.recommendations,
            view_actions=collector.view_actions,
        )

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[dict]:
        """Run one chat turn, yielding SSE-shaped events as the model streams.

        Event shapes (the endpoint serializes each as one SSE ``data:`` line):
          - ``{"type": "delta", "text": <fragment>}`` per streamed token.
          - ``{"type": "final", ...}`` once: the full reply plus the structured
            extras (tool_calls / pending_actions / recommendations) collected
            during the turn — same payload as :meth:`chat`.
          - ``{"type": "error", "message": <str>}`` if the SDK run fails.

        Availability is validated up front so an unconfigured assistant raises
        before the stream opens (the endpoint maps it to 503).
        """
        self.ensure_available()

        collector = TurnCollector()
        ctx = build_tool_context(
            stocks=self._stocks,
            watchlist=self._watchlist,
            portfolio=self._portfolio,
            holdings=self._holdings,
            collector=collector,
        )
        options = agent_runner.build_options(
            self._settings, ctx, SYSTEM_PROMPT, stream_partial=True
        )
        prompt = _serialize_conversation(messages)

        reply = ""
        try:
            async for event in agent_runner.run_agent_stream(prompt, options):
                if event["type"] == "delta":
                    yield {"type": "delta", "text": event["text"]}
                elif event["type"] == "result":
                    reply = event["text"]
        except AssistantAPIError as exc:
            logger.warning("assistant stream failed", extra={"detail": str(exc)})
            yield {"type": "error", "message": "AI 요청 처리 중 오류가 발생했습니다."}
            return

        if not reply:
            reply = "요청을 처리하지 못했습니다. 다시 시도해 주세요."

        final = ChatResponse(
            reply=reply,
            tool_calls=collector.tool_calls,
            pending_actions=collector.pending_actions,
            recommendations=collector.recommendations,
            view_actions=collector.view_actions,
        )
        yield {"type": "final", **final.model_dump()}

    async def confirm(self, action: PendingAction) -> ConfirmResponse:
        """Execute a previously proposed mutate action — no model involved."""
        self.ensure_available()
        if action.tool not in MUTATE_TOOLS:
            raise InvalidActionError(action.tool)

        result, message = await execute_mutate_action(action, self._watchlist)
        return ConfirmResponse(ok=True, tool=action.tool, result=result, message=message)


def _serialize_conversation(messages: list[ChatMessage]) -> str:
    """Fold client-owned history into a single prompt (§4.3a, Phase 1).

    The latest user turn is the live request; prior turns are replayed as
    labeled context so the stateless server reconstructs the thread.
    """
    if len(messages) == 1 and messages[0].role == ChatRole.USER:
        return messages[0].content

    lines: list[str] = ["이전 대화:"]
    for msg in messages[:-1]:
        speaker = "사용자" if msg.role == ChatRole.USER else "어시스턴트"
        lines.append(f"{speaker}: {msg.content}")
    last = messages[-1]
    lines.append("")
    lines.append(f"현재 사용자 요청: {last.content}")
    return "\n".join(lines)
