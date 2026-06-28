'use client';

import { useEffect, useRef, useState, type KeyboardEvent } from 'react';

import { useAssistant } from '@/stores/assistant';

interface ComposerProps {
  onSend: (content: string) => void;
}

// Textarea + send button. Enter sends, Shift+Enter inserts a newline. Disabled
// while a turn is in flight. The composer is also a controlled prefill target:
// recommendation cards seed a follow-up via the store's draft mechanism.
export default function Composer({ onSend }: ComposerProps) {
  const [value, setValue] = useState('');
  const isSending = useAssistant((s) => s.isSending);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus the composer when the panel mounts (panel open).
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || isSending) return;
    onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex items-end gap-2 border-t border-gray-200 p-3">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder="메시지 입력…"
        disabled={isSending}
        className="max-h-28 flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-gray-50"
      />
      <button
        type="button"
        onClick={submit}
        disabled={isSending || value.trim().length === 0}
        aria-label="전송"
        className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
      >
        ↑
      </button>
    </div>
  );
}
