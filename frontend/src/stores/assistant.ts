import { create } from 'zustand';

import type { ConversationEntry, PendingAction } from '@/types/assistant';

// Global store for the floating AI assistant. Holds the open/closed state and
// the conversation the client owns and replays to the backend each turn
// (stateless server). Conversation lives in memory for the session only —
// a reload clears it (Phase 1 has no persistence). Backend contract:
// `.aicontext/spec/backend/ASSISTANT.md`.

let entrySeq = 0;
function nextEntryId(): string {
  entrySeq += 1;
  return `entry_${entrySeq}`;
}

interface AssistantState {
  isOpen: boolean;
  entries: ConversationEntry[];
  // The single live pending action (only one at a time). Sending a new message
  // implicitly cancels it.
  pendingAction: PendingAction | null;
  // True while a chat/confirm round-trip is in flight (disables the composer).
  isSending: boolean;

  open: () => void;
  close: () => void;
  toggle: () => void;
  appendEntry: (entry: Omit<ConversationEntry, 'id'>) => void;
  // Append a new entry and return its id, so streaming callers can target it.
  appendEntryWithId: (entry: Omit<ConversationEntry, 'id'>) => string;
  // Patch an existing entry in place (used to accumulate streamed tokens and to
  // attach the final recommendations / pending action once the stream ends).
  updateEntry: (id: string, patch: Partial<Omit<ConversationEntry, 'id'>>) => void;
  // Append text to an existing entry's content (one streamed delta).
  appendToEntry: (id: string, text: string) => void;
  setPendingAction: (action: PendingAction | null) => void;
  setSending: (sending: boolean) => void;
  reset: () => void;
}

export const useAssistant = create<AssistantState>((set) => ({
  isOpen: false,
  entries: [],
  pendingAction: null,
  isSending: false,

  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  appendEntry: (entry) =>
    set((state) => ({ entries: [...state.entries, { ...entry, id: nextEntryId() }] })),
  appendEntryWithId: (entry) => {
    const id = nextEntryId();
    set((state) => ({ entries: [...state.entries, { ...entry, id }] }));
    return id;
  },
  updateEntry: (id, patch) =>
    set((state) => ({
      entries: state.entries.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    })),
  appendToEntry: (id, text) =>
    set((state) => ({
      entries: state.entries.map((e) =>
        e.id === id ? { ...e, content: e.content + text } : e,
      ),
    })),
  setPendingAction: (action) => set({ pendingAction: action }),
  setSending: (sending) => set({ isSending: sending }),
  reset: () => set({ entries: [], pendingAction: null, isSending: false }),
}));
