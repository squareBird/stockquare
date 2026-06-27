"""Assistant service — orchestrates the Claude Agent SDK over local Claude Code.

Owns no business logic: it builds the per-request tool context, runs one agent
turn through :mod:`app.services.agent_runner`, and assembles the response from
the model's text reply plus the request-scoped :class:`TurnCollector`. The
mutate gate denies `add_to_watchlist` inline and surfaces it as a
`PendingAction`; `/confirm` executes it directly without the model.

See `.aicontext/spec/backend/ASSISTANT.md`.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.exceptions import (
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
from app.services import agent_runner
from app.services.assistant_tools import (
    MUTATE_TOOLS,
    TurnCollector,
    build_tool_context,
    execute_mutate_action,
)
from app.services.stocks import StocksService
from app.services.watchlist import WatchlistService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "당신은 Stockquare의 한국 주식 투자 보조 AI입니다. "
    "항상 한국어로 간결하게 답하세요. "
    "제공된 Stockquare 도구만 사용하고 그 외 도구는 사용하지 마세요. "
    "종목은 항상 코드와 이름을 함께 언급하세요. "
    "추천 요청에는 rank_stocks 도구를 사용하세요. "
    "사용자가 관심종목 추가를 요청하면, 망설이지 말고 add_to_watchlist 도구를 "
    "호출하세요. 시스템이 자동으로 사용자 확인 절차를 처리하므로, 텍스트로만 "
    "'추가할까요?'라고 묻지 말고 반드시 도구를 호출해야 합니다. "
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
    ) -> None:
        self._settings = settings
        self._stocks = stocks
        self._watchlist = watchlist

    def _ensure_available(self) -> None:
        if not self._settings.assistant_enabled:
            raise AssistantNotConfiguredError("AI assistant is disabled")
        if not agent_runner.claude_code_available(self._settings):
            raise AssistantNotConfiguredError(
                "Local Claude Code not found. Install and log in to use the assistant."
            )

    async def chat(self, messages: list[ChatMessage]) -> ChatResponse:
        """Run one chat turn and return reply + tool activity + pending actions."""
        self._ensure_available()

        collector = TurnCollector()
        ctx = build_tool_context(
            stocks=self._stocks,
            watchlist=self._watchlist,
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
        )

    async def confirm(self, action: PendingAction) -> ConfirmResponse:
        """Execute a previously proposed mutate action — no model involved."""
        self._ensure_available()
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
