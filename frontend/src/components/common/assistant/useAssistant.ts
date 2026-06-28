'use client';

import { useCallback } from 'react';

import { useRouter } from 'next/navigation';

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { confirmAction, sendChat, streamChat } from '@/lib/api/assistant';
import { ApiError } from '@/lib/api/client';
import { useAssistant } from '@/stores/assistant';
import type { ChatMessage, ChatResponse, PendingAction, ViewAction } from '@/types/assistant';

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
  const appendEntryWithId = useAssistant((s) => s.appendEntryWithId);
  const updateEntry = useAssistant((s) => s.updateEntry);
  const appendToEntry = useAssistant((s) => s.appendToEntry);
  const setPendingAction = useAssistant((s) => s.setPendingAction);
  const setSending = useAssistant((s) => s.setSending);
  const queryClient = useQueryClient();
  const router = useRouter();

  // Act on a client-side view directive. `open_chart` navigates to the Trading
  // tab with the symbol/period so the inline chart renders there — the prose
  // reply carries the spoken summary, the chart is shown rather than tabulated.
  const applyViewActions = useCallback(
    (viewActions: ViewAction[]) => {
      const openChart = viewActions.find((a) => a.type === 'open_chart');
      if (!openChart) return;
      const symbol = openChart.params.symbol;
      if (typeof symbol !== 'string' || !symbol) return;
      const query = new URLSearchParams({ symbol });
      const name = openChart.params.name;
      if (typeof name === 'string' && name) query.set('name', name);
      const interval = openChart.params.interval;
      if (typeof interval === 'string' && interval) query.set('interval', interval);
      router.push(`/trading?${query.toString()}`);
    },
    [router],
  );

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

  // Fold a completed turn's structured extras into the assistant entry and
  // publish the live pending action. Shared by the streaming and fallback paths.
  const applyResponse = useCallback(
    (entryId: string, response: ChatResponse) => {
      const pending = response.pendingActions[0] ?? null;
      updateEntry(entryId, {
        // The streamed deltas already populated content; the final reply is the
        // authoritative text (covers the non-streaming fallback too).
        content: response.reply,
        recommendations: response.recommendations,
        pendingAction: pending,
      });
      setPendingAction(pending);
      applyViewActions(response.viewActions);
    },
    [applyViewActions, setPendingAction, updateEntry],
  );

  const send = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed) return;

      // Sending a new message implicitly cancels any live pending action.
      setPendingAction(null);
      appendEntry({ role: 'user', content: trimmed });
      const messages = buildHistory(trimmed);

      // Create the assistant entry up front; streamed tokens append into it so
      // the reply types out in real time.
      const entryId = appendEntryWithId({ role: 'assistant', content: '' });

      setSending(true);
      try {
        const response = await streamChat(messages, {
          onDelta: (text) => appendToEntry(entryId, text),
        });
        applyResponse(entryId, response);
      } catch (error) {
        // Streaming unavailable (e.g. proxy buffering / network) but the request
        // was otherwise valid: fall back to the non-streaming endpoint once.
        if (!(error instanceof ApiError) || error.status >= 500) {
          try {
            const response = await sendChat(messages);
            applyResponse(entryId, response);
            return;
          } catch (fallbackError) {
            updateEntry(entryId, {
              content:
                notConfiguredMessage(fallbackError) ??
                'AI 어시스턴트 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.',
              isError: true,
            });
            return;
          }
        }
        updateEntry(entryId, {
          content:
            notConfiguredMessage(error) ??
            'AI 어시스턴트 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.',
          isError: true,
        });
      } finally {
        setSending(false);
      }
    },
    [
      appendEntry,
      appendEntryWithId,
      appendToEntry,
      applyResponse,
      buildHistory,
      setPendingAction,
      setSending,
      updateEntry,
    ],
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
