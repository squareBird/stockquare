// Assistant API calls — conversational chat + mutate confirmation.
//
// Backend contract: `.aicontext/spec/backend/ASSISTANT.md`. The backend runs
// the user's local Claude Code via the Claude Agent SDK; from the frontend's
// perspective this is a normal non-streaming JSON endpoint.

import type { ChatMessage, ChatResponse, ConfirmResponse, PendingAction } from '@/types/assistant';

import { pendingActionToWire, toChatResponse, toConfirmResponse } from './adapters';
import { apiRequest } from './client';

export async function sendChat(messages: ChatMessage[]): Promise<ChatResponse> {
  const raw = await apiRequest<Parameters<typeof toChatResponse>[0]>('/api/v1/assistant/chat', {
    method: 'POST',
    body: { messages },
  });
  return toChatResponse(raw);
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
