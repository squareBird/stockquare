#!/usr/bin/env bash
# UserPromptSubmit hook: inject the project's Golden Rule checklist as context
# at the start of every command, so the rules are always in front of the model.
# Output JSON with hookSpecificOutput.additionalContext is appended to context.

read -r -d '' CTX <<'EOF'
[Project Golden Rule reminder — see .aicontext/guides/GOLDEN_RULE.md]
- Spec first: check .aicontext/spec/ before coding; no spec → write one and get approval.
- Follow .aicontext/patterns/ (backend: Ruff/Google style; frontend: TS strict, COMPONENT/STATE_MANAGEMENT).
- Tests required for services/ and api/ logic; KIS calls mocked. Tests must pass before done.
- Lint clean before committing (Ruff backend, ESLint frontend). No Any/any without justification.
- One logical change per commit; don't mix backend + frontend in one commit.
- Update the spec when implementation changes the contract.
- Subagent boundaries: backend edits backend/ only, frontend edits frontend/ only, devops owns infra.
EOF

jq -n --arg ctx "$CTX" \
  '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
