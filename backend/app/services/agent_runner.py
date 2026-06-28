"""Claude Agent SDK runner — the boundary the assistant service talks to.

Isolating the SDK call behind one function keeps `AssistantService` testable:
tests patch :func:`run_agent` to yield a canned message stream instead of
spawning the local Claude Code CLI. Nothing else in the app imports the SDK
loop directly.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

from app.core.config import Settings
from app.core.exceptions import AssistantAPIError
from app.services.assistant_tools import MCP_SERVER_NAME, ToolContext

logger = logging.getLogger(__name__)


def claude_code_available(settings: Settings) -> bool:
    """Best-effort check that the local Claude Code CLI is resolvable.

    Returns True when an explicit `assistant_cli_path` is set or a `claude`
    executable is on PATH. This does not verify the login session — an
    unauthenticated CLI surfaces later as an AssistantAPIError at request time.
    """
    if settings.assistant_cli_path:
        return True
    return shutil.which("claude") is not None


def build_options(settings: Settings, ctx: ToolContext, system_prompt: str) -> ClaudeAgentOptions:
    """Build the locked-down SDK options for one chat turn (§5.2)."""
    return ClaudeAgentOptions(
        mcp_servers={MCP_SERVER_NAME: ctx.server},
        allowed_tools=ctx.allowed_tool_names,
        tools=[],  # remove ALL built-in tools (Bash/Read/Write/...) from context
        setting_sources=[],  # do not load user ~/.claude settings / CLAUDE.md / skills
        permission_mode="default",  # unmatched tools route to can_use_tool
        can_use_tool=ctx.can_use_tool,
        system_prompt=system_prompt,
        max_turns=settings.assistant_max_turns,
        max_budget_usd=settings.assistant_max_budget_usd,
        model=settings.assistant_model,
        cli_path=settings.assistant_cli_path,
    )


async def _single_user_prompt(text: str) -> AsyncIterator[dict]:
    """Yield one streaming user message.

    The `can_use_tool` permission callback requires streaming mode, so the
    prompt must be an AsyncIterable of message dicts rather than a plain string
    (the SDK rejects a string prompt when `can_use_tool` is set).
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
        "session_id": "default",
    }


async def run_agent(prompt: str, options: ClaudeAgentOptions) -> str:
    """Run one agent turn and return the assistant's final text reply.

    Accumulates text blocks across AssistantMessages and prefers the
    ResultMessage's `result` when present. Any SDK / CLI failure is normalized
    to AssistantAPIError so the endpoint returns a clean 502.
    """
    reply_parts: list[str] = []
    final_result: str | None = None
    try:
        async for message in query(prompt=_single_user_prompt(prompt), options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        reply_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.is_error and not reply_parts and message.result is None:
                    raise AssistantAPIError(f"Assistant run failed: {message.subtype}")
                if message.result:
                    final_result = message.result
    except AssistantAPIError:
        raise
    except Exception as exc:  # noqa: BLE001 — normalize all SDK/CLI errors
        logger.warning("assistant SDK run failed", extra={"exc_type": type(exc).__name__})
        raise AssistantAPIError(str(exc)) from exc

    return (final_result or "\n".join(reply_parts)).strip()


# Expose the message stream iterator type alias for callers/tests.
AgentMessageStream = AsyncIterator[object]
