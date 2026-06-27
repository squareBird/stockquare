'use client';

import type { PendingAction } from '@/types/assistant';

interface ConfirmPromptProps {
  action: PendingAction;
  disabled: boolean;
  onConfirm: (action: PendingAction) => void;
  onCancel: () => void;
}

// Renders a proposed mutation (e.g. add to watchlist) with confirm/cancel.
// The mutation only runs on 확인 — the backend never executes it inline.
export default function ConfirmPrompt({
  action,
  disabled,
  onConfirm,
  onCancel,
}: ConfirmPromptProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
      <p className="text-gray-800">{action.summary}</p>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          onClick={() => onConfirm(action)}
          disabled={disabled}
          className="flex-1 rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-brand-700 disabled:opacity-60"
        >
          확인
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={disabled}
          className="flex-1 rounded-md bg-white px-3 py-1.5 text-xs font-medium text-gray-700 ring-1 ring-inset ring-gray-300 transition-colors hover:bg-gray-50 disabled:opacity-60"
        >
          취소
        </button>
      </div>
    </div>
  );
}
