# Golden Rule

The supreme rules of this project. Every task must comply with these rules. Read this document before starting any work.

## Quick Checklist

This is the canonical short form of the rules below. It is injected into every
prompt by `.claude/hooks/inject-golden-rule.sh`, which extracts the block between
the markers — keep it in sync by editing it here, never in the hook.

<!-- BEGIN GOLDEN-RULE-CHECKLIST -->
- Spec first: check `.aicontext/spec/` before coding; no spec → write one and get approval.
- Follow `.aicontext/patterns/` (backend: Ruff/Google style; frontend: TS strict, COMPONENT/STATE_MANAGEMENT).
- Tests required for `services/` and `api/` logic; KIS calls mocked. Tests must pass before done.
- Lint clean before committing (Ruff backend, ESLint frontend). No `Any`/`any` without justification.
- One logical change per commit; don't mix backend + frontend in one commit.
- Update the spec when implementation changes the contract.
- Subagent boundaries: backend edits `backend/` only, frontend edits `frontend/` only, devops owns infra.
- Language: all code, comments, docs, and commits in English; respond to the user in Korean.
<!-- END GOLDEN-RULE-CHECKLIST -->

## 1. Spec First

- Check the relevant spec in `.aicontext/spec/` before writing any code.
- If a spec does not exist for the feature, write the spec first and get approval.
- Never implement features that are not defined in a spec.

## 2. Follow Patterns

- All code must follow the patterns defined in `.aicontext/patterns/`.
- Patterns are split by side: `patterns/backend/` and `patterns/frontend/`.
- Backend (`patterns/backend/`): `CODE_STYLE.md` (naming, formatting, linting),
  `API_INTEGRATION.md`, `ERROR_HANDLING.md`, `REALTIME_DATA.md`.
- Frontend (`patterns/frontend/`): `CODE_STYLE.md`, `COMPONENT.md`,
  `STATE_MANAGEMENT.md`, `REALTIME_DATA.md`.
- When in doubt, check the pattern document first.

## 3. Pattern Validation

- After completing implementation, verify compliance with all relevant patterns.
- Run linters (Ruff for backend, ESLint for frontend) before committing.
- Review checklist:
  - [ ] Naming conventions followed
  - [ ] Type hints / TypeScript strict mode satisfied
  - [ ] Import order correct
  - [ ] Error handling follows the defined hierarchy
  - [ ] No `Any` / `any` usage without justification

## 4. Testing

- Write tests for all business logic in `services/`.
- Write tests for all API endpoints in `api/`.
- KIS API calls must be tested with mocked responses.
- Test file location mirrors source file location (e.g., `services/trading.py` → `tests/services/test_trading.py`).
- Tests must pass before committing.

## 5. Decision Records

Decisions are recorded in `.aicontext/decisions/`. Files are organized by topic, not chronologically. Related decisions accumulate within the same file.

### When to Record

- Do NOT record automatically. Only record when:
  - The user explicitly asks to record a decision.
  - You suggest "Should we record this decision?" and the user approves.
- At the end of a conversation that involved significant decisions, ask: "Should we record today's decisions?"

### What to Record

- Choosing between multiple alternatives (tools, libraries, architecture)
- Deciding NOT to do something
- Defining or changing project structure / design
- Selecting an external service or tool
- Reversing a previous decision

### What NOT to Record

- Code-level implementation details (belongs in code/commits)
- Trivial naming changes
- Bug fixes

### File Structure

Filename: `<topic>.md` (e.g., `tech-stack.md`, `trading.md`)

```
decisions/
├── tech-stack.md
├── project-structure.md
├── trading.md
└── analysis.md
```

### Entry Format

Each decision is an entry within the topic file:

```markdown
# Topic Name

## Decision Title
- Date: YYYY-MM-DD
- Options: Option A vs Option B vs ...
- Decision: What was chosen
- Reason: Why this option was selected over the others
```

## 6. Commit Discipline

- Follow the conventions in `GIT_CONVENTION.md`.
- One logical change per commit.
- Never commit code that fails linting or tests.

## 7. Documentation Sync

- When implementation changes a spec, update the spec.
- When a new pattern emerges, add it to the patterns directory.
- Stale documentation is worse than no documentation.

## 8. Subagent Boundaries

- Backend work (`backend/`) goes through the `backend` agent; it edits `backend/` only.
- Frontend work (`frontend/`) goes through the `frontend` agent; it edits `frontend/` only.
- Infra and shared resources (docker-compose, Dockerfiles, CI, env templates,
  deployment guide) go through the `devops` agent.
- The wire contract (request/response JSON shapes) is owned by the backend and
  consumed by the frontend via the adapter layer — change it deliberately and
  update both sides plus the spec.

## 9. Language

- All code, comments, documentation, and commit messages are written in English.
- Respond to the user in Korean.
