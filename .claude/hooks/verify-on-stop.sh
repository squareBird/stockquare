#!/usr/bin/env bash
# Stop hook: before finishing, verify lint/typecheck pass for the code that was
# actually touched this session. Blocks completion (decision:block) only when a
# check fails, feeding the failure back to the model to fix.
#
# Design notes:
# - We lint only the CHANGED files, not the whole tree, so a pre-existing error
#   elsewhere can't trap the session in a block loop. The check scope matches the
#   change scope (symmetric with lint-on-edit.sh, which is also per-file).
# - Backend typecheck (mypy/pyright) runs only if a checker is installed, so the
#   hook stays correct whether or not the project has adopted one yet.
# - Guard against infinite loops: if this hook already triggered a continuation
#   (stop_hook_active), do not block again.

INPUT=$(cat)
ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$ACTIVE" = "true" ]; then
  exit 0
fi

REPO="${CLAUDE_PROJECT_DIR:-/Users/squarebird/Repository/stockquare}"
cd "$REPO" || exit 0

# All files changed vs HEAD (tracked, staged, and untracked), deduped.
CHANGED=$( { git diff --name-only HEAD 2>/dev/null
            git diff --name-only --cached 2>/dev/null
            git ls-files --others --exclude-standard 2>/dev/null
          } | sort -u )

block() {
  jq -n --arg r "$1" '{decision: "block", reason: $r}'
  exit 0
}

# Changed files of a given grep pattern, restricted to those that still exist.
changed_files() {
  printf '%s\n' "$CHANGED" | grep -E "$1" | while read -r f; do
    [ -f "$f" ] && printf '%s\n' "$f"
  done
}

# --- Backend: Ruff lint on changed .py files only -------------------------
BACKEND_PY=$(changed_files '^backend/.*\.py$')
if [ -n "$BACKEND_PY" ]; then
  RUFF="$REPO/backend/.venv/bin/ruff"
  if [ -x "$RUFF" ]; then
    OUT=$(printf '%s\n' "$BACKEND_PY" | xargs "$RUFF" check 2>&1)
    if [ $? -ne 0 ]; then
      block "Backend Ruff check failed on changed files before finishing. Fix these lint errors, then stop:\n$OUT"
    fi
  fi

  # Backend typecheck — only if a checker is installed (no-op otherwise).
  MYPY="$REPO/backend/.venv/bin/mypy"
  PYRIGHT="$REPO/backend/.venv/bin/pyright"
  if [ -x "$MYPY" ]; then
    OUT=$( cd "$REPO/backend" && printf '%s\n' "$BACKEND_PY" | sed 's|^backend/||' | xargs "$MYPY" 2>&1 )
    if [ $? -ne 0 ]; then
      block "Backend mypy typecheck failed on changed files before finishing. Fix these type errors, then stop:\n$OUT"
    fi
  elif [ -x "$PYRIGHT" ]; then
    OUT=$( cd "$REPO/backend" && printf '%s\n' "$BACKEND_PY" | sed 's|^backend/||' | xargs "$PYRIGHT" 2>&1 )
    if [ $? -ne 0 ]; then
      block "Backend pyright typecheck failed on changed files before finishing. Fix these type errors, then stop:\n$OUT"
    fi
  fi
fi

# --- Frontend: typecheck (project-wide) + ESLint on changed files ---------
FRONTEND_SRC=$(changed_files '^frontend/src/.*\.(ts|tsx|js|jsx)$')
if [ -n "$FRONTEND_SRC" ]; then
  # tsc --noEmit is inherently project-wide; there is no reliable per-file mode.
  if [ -x "$REPO/frontend/node_modules/.bin/tsc" ]; then
    OUT=$( cd "$REPO/frontend" && npm run --silent typecheck 2>&1 )
    if [ $? -ne 0 ]; then
      block "Frontend typecheck (tsc --noEmit) failed before finishing. Fix these type errors, then stop:\n$OUT"
    fi
  fi

  ESLINT="$REPO/frontend/node_modules/.bin/eslint"
  if [ -x "$ESLINT" ]; then
    OUT=$( cd "$REPO/frontend" && printf '%s\n' "$FRONTEND_SRC" | sed 's|^frontend/||' | xargs "$ESLINT" 2>&1 )
    if [ $? -ne 0 ]; then
      block "Frontend ESLint failed on changed files before finishing. Fix these lint errors, then stop:\n$OUT"
    fi
  fi
fi

exit 0
