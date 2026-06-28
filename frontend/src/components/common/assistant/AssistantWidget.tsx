'use client';

import { useAssistant } from '@/stores/assistant';

import AssistantPanel from './AssistantPanel';

// Root of the floating assistant: a FAB when closed, the panel when open.
// Mounted once in Providers so it overlays every page without per-page wiring
// and never shifts page layout (fixed positioning, high z-index).
export default function AssistantWidget() {
  const isOpen = useAssistant((s) => s.isOpen);
  const open = useAssistant((s) => s.open);

  if (isOpen) return <AssistantPanel />;

  return (
    <button
      type="button"
      onClick={open}
      aria-label="AI 어시스턴트 열기"
      className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white shadow-lg transition-colors hover:bg-brand-700"
    >
      AI
    </button>
  );
}
