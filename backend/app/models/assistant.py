"""Assistant domain models (Pydantic) — chat / confirm wire contract.

See `.aicontext/spec/backend/ASSISTANT.md`. The assistant turns a
natural-language conversation into tool calls over existing services through
the Claude Agent SDK; these models are the HTTP surface only.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class ToolCallResult(BaseModel):
    """One tool the model invoked during the turn (success or failure)."""

    tool: str
    input: dict
    ok: bool
    error_code: str | None = None


class PendingAction(BaseModel):
    """A proposed mutation awaiting explicit user confirmation.

    The server is stateless; the client echoes this object back to
    `/confirm`, where `input` is re-validated against the tool schema before
    the wrapped service runs.
    """

    id: str
    tool: str
    summary: str
    input: dict


class Recommendation(BaseModel):
    """A stock the assistant surfaced, rendered as a card by the client."""

    symbol: str
    name: str
    price: int | None = None
    change_rate: float | None = None
    reason: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallResult] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    action: PendingAction


class ConfirmResponse(BaseModel):
    ok: bool
    tool: str
    result: dict
    message: str
