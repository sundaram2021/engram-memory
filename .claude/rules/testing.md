# Testing Rules

## Running Tests
- `pytest tests/ -x` — run all, exit on first failure.
- `pytest tests/test_engine.py -x` — run a specific file.

## Framework
- All tests are async: `pytest-asyncio` with `asyncio_mode = "auto"`.
- Shared fixtures live in `tests/conftest.py`: `storage` (tmp_path SQLite) and `engine` (with detection worker).

## Rules
- Run tests via shell command — never predict or simulate test results.
- No mocks — test against real `SQLiteStorage` using `tmp_path`. The storage fixture handles setup and teardown.
- New functionality must include tests. New schema changes must verify migrations on a fresh database.

## Test Quality
1. One logical assertion per test.
2. Test name describes the scenario (`test_commit_deduplicates_identical_content`).
3. Fast — use `tmp_path`, no network calls.
4. Independent — no test depends on another's state or ordering.
5. Repeatable — same result every run.

## Before Submitting
- `pytest tests/ -x` must pass.
- If you changed schema, run storage tests to verify migration path.
