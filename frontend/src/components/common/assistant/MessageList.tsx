'use client';

import { useEffect, useRef } from 'react';

import { useAssistant } from '@/stores/assistant';
import type { PendingAction, Recommendation } from '@/types/assistant';

import ConfirmPrompt from './ConfirmPrompt';
import RecommendationCard from './RecommendationCard';

interface MessageListProps {
  onConfirm: (action: PendingAction) => void;
  onCancel: () => void;
  onAddToWatchlist: (rec: Recommendation) => void;
}

const EXAMPLE_PROMPTS = ['등락률 상위 추천', '거래량 많은 종목', '관심종목 보여줘'];

export default function MessageList({ onConfirm, onCancel, onAddToWatchlist }: MessageListProps) {
  const entries = useAssistant((s) => s.entries);
  const pendingAction = useAssistant((s) => s.pendingAction);
  const isSending = useAssistant((s) => s.isSending);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the latest content on new entries / typing indicator.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries, isSending]);

  return (
    <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
      {entries.length === 0 ? (
        <div className="space-y-3 text-sm text-gray-500">
          <p>안녕하세요! 종목 추천이나 관심종목 관리를 도와드릴게요.</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_PROMPTS.map((prompt) => (
              <span
                key={prompt}
                className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
              >
                {prompt}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {entries.map((entry) => {
        const isUser = entry.role === 'user';
        return (
          <div key={entry.id} className="space-y-2">
            <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                  isUser
                    ? 'bg-brand-600 text-white'
                    : entry.isError
                      ? 'bg-red-50 text-red-700'
                      : 'bg-gray-100 text-gray-800'
                }`}
              >
                {entry.content}
              </div>
            </div>

            {entry.recommendations && entry.recommendations.length > 0 ? (
              <div className="space-y-2">
                {entry.recommendations.map((rec) => (
                  <RecommendationCard
                    key={rec.symbol}
                    recommendation={rec}
                    onAddToWatchlist={onAddToWatchlist}
                  />
                ))}
              </div>
            ) : null}

            {/* Render the confirm prompt only while it is still the live action. */}
            {entry.pendingAction && pendingAction?.id === entry.pendingAction.id ? (
              <ConfirmPrompt
                action={entry.pendingAction}
                disabled={isSending}
                onConfirm={onConfirm}
                onCancel={onCancel}
              />
            ) : null}
          </div>
        );
      })}

      {isSending ? (
        <div className="flex justify-start">
          <div className="rounded-2xl bg-gray-100 px-3 py-2 text-sm text-gray-400">
            입력 중…
          </div>
        </div>
      ) : null}

      <div ref={bottomRef} />
    </div>
  );
}
