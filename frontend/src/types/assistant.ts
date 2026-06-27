// Assistant domain types (camelCase). Wire types live in lib/api/assistant.ts;
// the adapter layer maps snake_case → these. Backend contract:
// `.aicontext/spec/backend/ASSISTANT.md`.

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ToolCallResult {
  tool: string;
  input: Record<string, unknown>;
  ok: boolean;
  errorCode?: string | null;
}

export interface PendingAction {
  id: string;
  tool: string;
  summary: string;
  input: Record<string, unknown>;
}

export interface Recommendation {
  symbol: string;
  name: string;
  price?: number | null;
  changeRate?: number | null;
  reason: string;
}

export interface ChatResponse {
  reply: string;
  toolCalls: ToolCallResult[];
  pendingActions: PendingAction[];
  recommendations: Recommendation[];
}

export interface ConfirmResponse {
  ok: boolean;
  tool: string;
  result: Record<string, unknown>;
  message: string;
}

// One rendered entry in the conversation. Assistant turns carry the structured
// extras (recommendations / pending action) alongside the prose so MessageList
// can render cards and the confirm prompt inline.
export interface ConversationEntry {
  id: string;
  role: ChatRole;
  content: string;
  recommendations?: Recommendation[];
  pendingAction?: PendingAction | null;
  isError?: boolean;
}
