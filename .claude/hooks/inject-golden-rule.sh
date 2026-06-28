#!/usr/bin/env bash
# UserPromptSubmit hook: inject the project's Golden Rule checklist as context
# at the start of every command, so the rules are always in front of the model.
#
# Single source of truth: the checklist lives in GOLDEN_RULE.md between the
# GOLDEN-RULE-CHECKLIST markers. We extract it here rather than duplicating it,
# so the injected reminder can never drift from the canonical document.
# Output JSON with hookSpecificOutput.additionalContext is appended to context.

REPO="${CLAUDE_PROJECT_DIR:-/Users/squarebird/Repository/stockquare}"
RULE_FILE="$REPO/.aicontext/guides/GOLDEN_RULE.md"

CHECKLIST=$(sed -n '/<!-- BEGIN GOLDEN-RULE-CHECKLIST -->/,/<!-- END GOLDEN-RULE-CHECKLIST -->/p' "$RULE_FILE" 2>/dev/null \
  | sed '1d;$d')

# Fall back to a minimal reminder if extraction fails (file moved/markers gone),
# so the hook degrades gracefully instead of injecting an empty block.
if [ -z "$CHECKLIST" ]; then
  CHECKLIST="- Read .aicontext/guides/GOLDEN_RULE.md before starting any work."
fi

CTX=$(printf '[Project Golden Rule reminder — see .aicontext/guides/GOLDEN_RULE.md]\n%s' "$CHECKLIST")

jq -n --arg ctx "$CTX" \
  '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
