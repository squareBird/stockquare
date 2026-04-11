# tests/services/

This directory intentionally contains no `test_*.py` files.

Every method in `app/services/{portfolio,watchlist,market,stocks}.py` is
exercised end-to-end by the routing tests under `tests/api/`, which build
a real FastAPI app and override the `_get_service` dependency to inject a
live service instance bound to a `FakeKISClient` (`tests/conftest.py`)
and an in-memory SQLite session. The resulting assertions run through
the full request lifecycle — router → service → KIS stub → DB — so
service logic is covered without a parallel set of direct unit tests.

GOLDEN_RULE §4 asks for test files that mirror the source layout. That
rule is about **coverage locality**, not test duplication. Adding thin
passthrough tests here would provide no additional signal and would have
to be kept in sync with two changing surfaces. The conscious decision
for Phase 1 is:

- Business logic coverage → `tests/api/test_{portfolio,watchlist,market,stocks}.py`
- KIS client coverage → `tests/kis/test_token.py` (the non-trivial unit)
- Cross-cutting → `tests/test_config.py`, `tests/test_cors.py`

If a service method ever needs unit-level isolation (e.g., complex
pure-function helpers that do not touch KIS or the DB), add a focused
test module here at that time. Until then, keep this README as the
marker that the empty directory is deliberate.
