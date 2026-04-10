# Golden Rule

The supreme rules of this project. Every task must comply with these rules. Read this document before starting any work.

## 1. Spec First

- Check the relevant spec in `.aicontext/spec/` before writing any code.
- If a spec does not exist for the feature, write the spec first and get approval.
- Never implement features that are not defined in a spec.

## 2. Follow Patterns

- All code must follow the patterns defined in `.aicontext/patterns/`.
- `CODE_STYLE.md` — naming, formatting, linting rules.
- `API_INTEGRATION.md`, `ERROR_HANDLING.md`, `REALTIME_DATA.md` — backend implementation patterns.
- `STATE_MANAGEMENT.md`, `COMPONENT.md`, `REALTIME_DATA.md` — frontend implementation patterns.
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
