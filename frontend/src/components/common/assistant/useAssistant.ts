'use client';

import { useCallback } from 'react';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api/client';
import { confirmAction, sendChat } from '@/lib/api/assistant';
import { useAssistant } from '@/stores/assistant';
import type { ChatMessage, PendingAction } from '@/types/assistant';

// Orchestrates the assistant conversation: builds the message history from the
// store, calls the chat / confirm endpoints, and folds responses back into the
// store. React Query mutations (not queries) because these are user-triggered
// POSTs. Backend contract: `.aicontext/spec/backend/ASSISTANT.md`.

function notConfiguredMessage(error: unknown): string | null {
  if (error instanceof ApiError && error.status === 503) {
    return 'AI 어시스턴트를 사용할 수 없습니다. 로컬 Claude Code 설치 및 로그인 상태를 확인해 주세요.';
  }
  return null;
}

export function useAssistantChat() {
  const entries = useAssistant((s) => s.entries);
  const appendEntry = useAssistant((s) => s.appendEntry);
  const setPendingAction = useAssistant((s) => s.setPendingAction);
  const setSending = useAssistant((s) => s.setSending);
  const queryClient = useQueryClient();

  const chatMutation = useMutation({
    mutationFn: (messages: ChatMessage[]) => sendChat(messages),
  });

  const confirmMutation = useMutation({
    mutationFn: (action: PendingAction) => confirmAction(action),
  });

  // Build the wire history from the rendered conversation (user + assistant
  // prose only; cards/prompts are derived server-side each turn).
  const buildHistory = useCallback(
    (nextUserContent: string): ChatMessage[] => {
      const history: ChatMessage[] = entries
        .filter((e) => !e.isError)
        .map((e) => ({ role: e.role, content: e.content }));
      history.push({ role: 'user', content: nextUserContent });
      return history;
    },
    [entries],
  );

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;

      // Sending a new message implicitly cancels any live pending action.
      setPendingAction(null);
      appendEntry({ role: 'user', content: trimmed });
      const messages = buildHistory(trimmed);

      setSending(true);
      try {
        const response = await chatMutation.mutateAsync(messages);
        const pending = response.pendingActions[0] ?? null;
        appendEntry({
          role: 'assistant',
          content: response.reply,
          recommendations: response.recommendations,
          pendingAction: pending,
        });
        setPendingAction(pending);
      } catch (error) {
        const notConfigured = notConfiguredMessage(error);
        appendEntry({
          role: 'assistant',
          content:
            notConfigured ??
            'AI 어시스턴트 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.',
          isError: true,
        });
      } finally {
        setSending(false);
      }
    },
    [appendEntry, buildHistory, chatMutation, setPendingAction, setSending],
  );

  const confirm = useCallback(
    async (action: PendingAction) => {
      setSending(true);
      try {
        const response = await confirmMutation.mutateAsync(action);
        appendEntry({ role: 'assistant', content: response.message });
        setPendingAction(null);
        // Refresh any watchlist-backed views (dashboard, trading lists).
        queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      } catch (error) {
        const notConfigured = notConfiguredMessage(error);
        appendEntry({
          role: 'assistant',
          content: notConfigured ?? '작업을 완료하지 못했습니다. 다시 시도해 주세요.',
          isError: true,
        });
        setPendingAction(null);
      } finally {
        setSending(false);
      }
    },
    [appendEntry, confirmMutation, queryClient, setPendingAction, setSending],
  );

  const cancelPending = useCallback(() => {
    setPendingAction(null);
    appendEntry({ role: 'assistant', content: '취소했습니다.' });
  }, [appendEntry, setPendingAction]);

  return { send, confirm, cancelPending };
}
