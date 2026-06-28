// Assistant API calls — conversational chat + mutate confirmation.
//
// Backend contract: `.aicontext/spec/backend/ASSISTANT.md`. The backend runs
// the user's local Claude Code via the Claude Agent SDK; from the frontend's
// perspective this is a normal non-streaming JSON endpoint.

import type { ChatMessage, ChatResponse, ConfirmResponse, PendingAction } from '@/types/assistant';

import { pendingActionToWire, toChatResponse, toConfirmResponse } from './adapters';
import { ApiError, apiRequest, API_BASE_URL } from './client';

export async function sendChat(messages: ChatMessage[]): Promise<ChatResponse> {
  const raw = await apiRequest<Parameters<typeof toChatResponse>[0]>('/api/v1/assistant/chat', {
    method: 'POST',
    body: { messages },
  });
  return toChatResponse(raw);
}

// Server-Sent Events from `/chat/stream`. The backend emits one JSON object per
// `data:` line: `{type:'delta',text}` per token, a single `{type:'final',...}`
// with the structured extras (same shape as ChatResponse), or `{type:'error'}`.
type StreamEvent =
  | { type: 'delta'; text: string }
  | { type: 'error'; message: string }
  | ({ type: 'final' } & Parameters<typeof toChatResponse>[0]);

export interface StreamHandlers {
  onDelta: (text: string) => void;
  signal?: AbortSignal;
}

// Stream a chat turn. Invokes `onDelta` per token as it arrives and resolves
// with the final ChatResponse. Throws ApiError (e.g. 503) before any delta when
// the backend rejects the request, so the caller can fall back to `sendChat`.
export async function streamChat(
  messages: ChatMessage[],
  handlers: StreamHandlers,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/assistant/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
    signal: handlers.signal,
  });

  if (!response.ok || !response.body) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      /* non-JSON error body */
    }
    const message =
      typeof body === 'object' && body !== null && 'message' in body
        ? String((body as { message: unknown }).message)
        : `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message, body);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let final: ChatResponse | null = null;

  // SSE frames are separated by a blank line; a frame's payload is its
  // `data:` lines joined. We split on the buffer's newlines and parse each
  // `data:` line independently (the backend writes one JSON object per line).
  const handleLine = (line: string) => {
    if (!line.startsWith('data:')) return;
    const payload = line.slice(line.indexOf(':') + 1).trim();
    if (!payload) return;
    const event = JSON.parse(payload) as StreamEvent;
    if (event.type === 'delta') {
      handlers.onDelta(event.text);
    } else if (event.type === 'final') {
      final = toChatResponse(event);
    } else if (event.type === 'error') {
      throw new ApiError(502, event.message, event);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      handleLine(line.replace(/\r$/, ''));
    }
  }
  // Flush any trailing line without a terminating newline.
  if (buffer.trim()) handleLine(buffer.replace(/\r$/, ''));

  if (!final) {
    throw new ApiError(502, 'Stream ended without a final event', null);
  }
  return final;
}

export async function confirmAction(action: PendingAction): Promise<ConfirmResponse> {
  const raw = await apiRequest<Parameters<typeof toConfirmResponse>[0]>(
    '/api/v1/assistant/confirm',
    {
      method: 'POST',
      body: { action: pendingActionToWire(action) },
    },
  );
  return toConfirmResponse(raw);
}
