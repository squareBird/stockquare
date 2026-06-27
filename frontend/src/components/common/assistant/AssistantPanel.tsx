'use client';

import { useCallback, useEffect } from 'react';

import { useAssistant } from '@/stores/assistant';
import type { Recommendation } from '@/types/assistant';

import Composer from './Composer';
import MessageList from './MessageList';
import { useAssistantChat } from './useAssistant';

// The open chat card: header, scrollable message list, composer. Anchored
// bottom-right on desktop, near-full-screen on mobile. Esc closes the panel.
export default function AssistantPanel() {
  const close = useAssistant((s) => s.close);
  const { send, confirm, cancelPending } = useAssistantChat();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [close]);

  // "관심종목 추가" on a card seeds a natural-language follow-up turn so the
  // assistant proposes the mutation through the normal confirm gate.
  const handleAddToWatchlist = useCallback(
    (rec: Recommendation) => {
      send(`${rec.name}(${rec.symbol})를 관심종목에 추가해줘`);
    },
    [send],
  );

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label="AI 어시스턴트"
      className="fixed bottom-0 right-0 z-50 flex h-[80vh] max-h-[560px] w-full flex-col rounded-t-2xl bg-white shadow-2xl sm:bottom-6 sm:right-6 sm:h-[560px] sm:w-[380px] sm:rounded-2xl"
    >
      <header className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">AI 어시스턴트</h2>
        <button
          type="button"
          onClick={close}
          aria-label="AI 어시스턴트 닫기"
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          ✕
        </button>
      </header>

      <MessageList
        onConfirm={confirm}
        onCancel={cancelPending}
        onAddToWatchlist={handleAddToWatchlist}
      />

      <Composer onSend={send} />
    </div>
  );
}
