"""Assistant domain — Claude Agent SDK orchestration over local Claude Code.

Modules:
  - service.py : AssistantService (chat / chat_stream / confirm)
  - tools.py   : in-process MCP tool registry + mutate gate
  - runner.py  : the Claude Agent SDK boundary (run_agent / run_agent_stream)
"""

from app.services.assistant.service import AssistantService

__all__ = ["AssistantService"]
