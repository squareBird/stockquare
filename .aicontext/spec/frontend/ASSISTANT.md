# Assistant Spec (Frontend)

A floating **AI assistant** available on every page. A circular button anchored
bottom-right opens a chat panel where the user types natural-language requests
("등락률 상위 조건으로 추천종목 알려줘", "추천 종목들 관심종목에 추가해줘") and
the assistant replies, surfaces recommendation cards, and asks for confirmation
before any mutation. This is the frontend for backend `ASSISTANT.md`.

Not a route — a global overlay mounted once in `Providers`, so it persists
across navigation.

> **Scope (Phase 1).** Non-streaming chat (full reply per turn), recommendation
> cards, and a confirm gate for the single mutate action `add_to_watchlist`.
> No streaming tokens, no conversation persistence across reloads, no order
> placement. Conversation lives in client memory for the session only.

## Layout

```
                                  ┌───────────────────────────────┐
                                  │  AI 어시스턴트            [✕]  │
                                  ├───────────────────────────────┤
                                  │  (messages, scroll)           │
                                  │   ┌─────────────────────────┐ │
                                  │   │ user: 등락률 상위 추천   │ │
                                  │   └─────────────────────────┘ │
                                  │   assistant: 5개 종목입니다…  │
                                  │   ┌── RecommendationCard ──┐  │
                                  │   │ 삼성전자 005930 +5.1%  │  │
                                  │   │ [관심종목 추가]         │  │
                                  │   └────────────────────────┘  │
                                  │   ┌── ConfirmPrompt ───────┐  │
                                  │   │ 2종목 추가할까요?       │  │
                                  │   │ [확인]  [취소]          │  │
                                  │   └────────────────────────┘  │
                                  ├───────────────────────────────┤
                                  │ [메시지 입력…            ] [↑] │
                                  └───────────────────────────────┘
        page content …                              ╭───╮
                                                     │ AI│  ← FAB (closed state)
                                                     ╰───╯
```

- **Closed**: a circular FAB, `fixed bottom-6 right-6 z-50`, brand-colored,
  with an AI/chat icon and `aria-label="AI 어시스턴트 열기"`.
- **Open**: a panel anchored bottom-right. On `sm:` and up it is a fixed-size
  card (`~380×560px`, `max-h-[80vh]`); on mobile it expands to near-full-screen.
- Closing keeps the conversation in memory (re-opening shows history); a
  reload clears it (Phase 1 has no persistence).

## Entry point / mounting

- Mount `<AssistantWidget />` once in `src/app/providers.tsx`, sibling to
  `<StockDetailModal />`, so it overlays every page without per-page wiring.
- It must not shift page layout (fixed positioning, high `z-index`).

## State management

Follows the project pattern (Zustand for UI/session state, React Query for
server calls):

- `stores/assistant.ts` (Zustand): `isOpen`, `messages` (the conversation the
  client owns and replays), `pendingAction`, plus actions `open/close/toggle`,
  `appendMessage`, `setPendingAction`, `reset`. This is the source of truth for
  the conversation that gets sent to the backend each turn.
- React Query **mutations** for the network calls (not queries — these are
  user-triggered POSTs):
  - `useSendMessage` → `POST /api/v1/assistant/chat`
  - `useConfirmAction` → `POST /api/v1/assistant/confirm`
  Both live in `app/_hooks` or `hooks/useAssistant.ts` (co-located with the
  widget under `components/common/assistant/` is acceptable since it is global).

## API client + adapters

- `lib/api/assistant.ts`: `sendChat(messages)` and `confirmAction(action)`,
  using the shared `client.ts` fetch wrapper (same as `watchlist.ts`).
- Map snake_case wire types → camelCase domain types in `lib/api/adapters.ts`
  (e.g. `change_rate → changeRate`, `pending_actions → pendingActions`),
  consistent with the existing adapter layer.
- Types in `types/assistant.ts`: `ChatMessage`, `ToolCallResult`,
  `PendingAction`, `Recommendation`, `ChatResponse`, `ConfirmResponse`.

## Components

Under `components/common/assistant/`:

| Component | Role |
|-----------|------|
| `AssistantWidget` | Root: renders FAB when closed, panel when open; reads `isOpen` from the store. |
| `AssistantPanel` | The open chat card: header, scrollable message list, composer. |
| `MessageList` | Renders the conversation: user bubbles, assistant bubbles, recommendation cards, confirm prompts. Auto-scrolls to bottom on new content. |
| `RecommendationCard` | One recommended stock: name + symbol + price + `ChangeDisplay` (reuse existing `common/ChangeDisplay`), with an inline "관심종목 추가" affordance that seeds a follow-up turn. |
| `ConfirmPrompt` | Renders a `pendingAction.summary` with `[확인]` / `[취소]`. 확인 → `useConfirmAction`; 취소 → clears the pending action and appends a system note. |
| `Composer` | Textarea + send button. Enter sends, Shift+Enter newlines. Disabled while a turn is in flight. |

Reuse existing primitives: `ChangeDisplay`, `PriceDisplay`, `SignalBadge` where
they fit. Do not re-implement formatting — use `lib/format.ts`.

## Interaction flow

1. User types → `appendMessage({role:'user'})` → `useSendMessage(messages)`.
2. On response: append `{role:'assistant', content: reply}`; render
   `recommendations` as cards; if `pendingActions` non-empty, store the first as
   `pendingAction` and render a `ConfirmPrompt`.
3. 확인 → `useConfirmAction(pendingAction)`; on success append the
   `ConfirmResponse.message` as an assistant note, clear `pendingAction`, and
   invalidate the `watchlist` query so the dashboard/trading lists refresh.
4. 취소 → clear `pendingAction`, append "취소했습니다." note.
5. A turn in flight shows a typing indicator and disables the composer.

Only one `pendingAction` is live at a time; sending a new message while one is
pending implicitly cancels it.

## States & degradation

- **Loading**: typing indicator bubble; composer disabled.
- **Tool failures**: backend returns them inside the reply prose — no special
  client handling beyond rendering the text (failed tools are not cards).
- **503 `ASSISTANT_NOT_CONFIGURED`**: show a non-blocking inline notice
  ("AI 어시스턴트가 아직 설정되지 않았습니다.") and keep the panel usable for
  retry; do not crash the app. The FAB still renders.
- **502 `ASSISTANT_API_ERROR`**: append an assistant-style error bubble with a
  retry affordance; preserve the user's last message.
- **Empty state**: on first open, a short greeting + 2–3 example prompt chips
  ("등락률 상위 추천", "관심종목 보여줘") the user can tap to prefill.

## Accessibility

- FAB and close button have `aria-label`s; panel uses `role="dialog"` +
  `aria-modal` semantics appropriate for a non-blocking overlay.
- Esc closes the panel; focus moves into the composer on open and returns to the
  FAB on close.
- Confirm/cancel are real buttons, keyboard-operable.

## Phasing

- **Phase 1** — FAB + panel, non-streaming chat, recommendation cards, confirm
  gate for `add_to_watchlist`, session-only memory.
- **Phase 2** — SSE streaming (render tokens as they arrive), persisted
  conversation history, richer cards (mini chart via `SymbolChart`).
- **Phase 3** — Strategy creation from chat and (gated) order actions, mirroring
  backend `ASSISTANT.md` §9.
