#!/usr/bin/env bash
# PreToolUse hook for Bash: block dangerous / secret-leaking commands.
# Emits a PreToolUse deny decision when the command matches a danger pattern.

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')

deny() {
  jq -n --arg r "$1" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  exit 0
}

# Destructive recursive deletes targeting broad paths.
if printf '%s' "$CMD" | grep -Eq 'rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r?)[[:space:]]+(/|~|\$HOME|\.\.|\*|/\*)'; then
  deny "Refusing dangerous recursive delete: '$CMD'. Narrow the target or run it yourself if intended."
fi

# git add of secret files, or committing .env.
if printf '%s' "$CMD" | grep -Eq 'git[[:space:]]+add.*(\.env([^.]|$)|/\.env|secrets/)'; then
  deny "Refusing to 'git add' a secret/.env path: '$CMD'."
fi

# Printing real env files to stdout (potential secret leak into transcript):
# a file-reading command that references a .env token (.env, .env.local, ...).
if printf '%s' "$CMD" | grep -Eq '(^|[[:space:]])(cat|less|more|head|tail|bat|xxd|od)[[:space:]]' \
   && printf '%s' "$CMD" | grep -Eq '(^|[[:space:]]|/)\.env([^a-zA-Z0-9]|$)' \
   && ! printf '%s' "$CMD" | grep -Eq '\.env\.example'; then
  deny "Refusing to print a real .env file: '$CMD'. It may contain credentials (\.env.example templates are fine)."
fi

exit 0
