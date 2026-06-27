#!/usr/bin/env bash
# PreToolUse hook for Write|Edit: block edits to protected files.
# NOTE: the hook payload carries NO subagent identity (verified empirically),
# so cross-agent boundary enforcement (frontend must not touch backend/, etc.)
# CANNOT live here — it stays in .claude/agents/*.md. This hook enforces only
# the identity-independent rules: never edit real secret files.
#
# Emits a PreToolUse permission decision: deny (with reason) or allow (silent).

INPUT=$(cat)
FILE=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

deny() {
  jq -n --arg r "$1" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  exit 0
}

# Block edits to real env / secret files. .env.example templates are allowed.
case "$FILE" in
  *.env.example) : ;;  # templates are fine
  *.env|*.env.*|*/.env|*/.env.local|*/.env.production)
    deny "Refusing to edit secret file '$FILE'. Real env files hold credentials — only *.env.example templates may be edited (devops agent owns those)." ;;
esac

# Block edits to common secret material.
case "$FILE" in
  */secrets/*|*id_rsa|*id_ed25519|*.pem|*.key|*/.aws/credentials|*/.claude/.credentials.json)
    deny "Refusing to edit credential file '$FILE'." ;;
esac

# Allow everything else (silent — no output means proceed).
exit 0
