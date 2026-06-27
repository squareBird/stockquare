#!/usr/bin/env bash
# Stop hook: before finishing, verify lint passes for whichever side has
# uncommitted changes. Blocks completion (exit 2 semantics via decision:block)
# only when a check fails, feeding the failure back to the model to fix.
#
# Guard against infinite loops: if this hook already triggered a continuation
# (stop_hook_active), do not block again.

INPUT=$(cat)
ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$ACTIVE" = "true" ]; then
  exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-/Users/squarebird/Repository/stockquare}"
cd "$REPO" || exit 0

CHANGED=$(git diff --name-only HEAD 2>/dev/null; git diff --name-only --cached 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)

block() {
  jq -n --arg r "$1" '{decision: "block", reason: $r}'
  exit 0
}

# Backend: lint changed .py files.
if printf '%s' "$CHANGED" | grep -Eq '^backend/.*\.py$'; then
  RUFF="$REPO/backend/.venv/bin/ruff"
  if [ -x "$RUFF" ]; then
    OUT=$("$RUFF" check backend/ 2>&1)
    if [ $? -ne 0 ]; then
      block "Backend Ruff check failed before finishing. Fix these lint errors, then stop:\n$OUT"
    fi
  fi
fi

# Frontend: typecheck + lint when src changed.
if printf '%s' "$CHANGED" | grep -Eq '^frontend/src/.*\.(ts|tsx|js|jsx)$'; then
  if [ -x "$REPO/frontend/node_modules/.bin/tsc" ]; then
    OUT=$( cd "$REPO/frontend" && npm run --silent typecheck 2>&1 )
    if [ $? -ne 0 ]; then
      block "Frontend typecheck (tsc --noEmit) failed before finishing. Fix these type errors, then stop:\n$OUT"
    fi
  fi
fi

exit 0
