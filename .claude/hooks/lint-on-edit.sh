#!/usr/bin/env bash
# PostToolUse hook for Write|Edit: auto-lint the edited file.
# Backend .py  -> Ruff format + lint --fix on that file.
# Frontend ts/tsx/js/jsx -> ESLint --fix on that file.
# Non-blocking: prints a short note; never fails the turn.

INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$FILE" ] && exit 0
[ -f "$FILE" ] || exit 0

REPO="${CLAUDE_PROJECT_DIR:-/Users/squarebird/Repository/stockquare}"

case "$FILE" in
  "$REPO"/backend/*.py)
    RUFF="$REPO/backend/.venv/bin/ruff"
    if [ -x "$RUFF" ]; then
      "$RUFF" format "$FILE" >/dev/null 2>&1
      "$RUFF" check --fix "$FILE" >/dev/null 2>&1
    fi
    ;;
  "$REPO"/frontend/*.ts|"$REPO"/frontend/*.tsx|"$REPO"/frontend/*.js|"$REPO"/frontend/*.jsx)
    ESLINT="$REPO/frontend/node_modules/.bin/eslint"
    if [ -x "$ESLINT" ]; then
      ( cd "$REPO/frontend" && "$ESLINT" --fix "$FILE" >/dev/null 2>&1 )
    fi
    ;;
esac
exit 0
