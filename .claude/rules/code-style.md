# Code Style Rules

## Python
- Python 3.11+ required. Use `|` union syntax, not `Union`.
- Ruff for linting: `target-version = py311`, `line-length = 100`.
- `from __future__ import annotations` at the top of every file.
- Type hints on all function signatures (params and return types).
- Data is passed as `dict[str, Any]` — do not introduce Pydantic models without discussion.

## Async
- All storage and engine operations must be `async def`.
- Use `aiosqlite` for SQLite, `asyncpg` for PostgreSQL.
- Never block the event loop with synchronous I/O or `time.sleep`.
- Background tasks (conflict detection worker) run as async coroutines.

## Datetime
- Use `datetime.now(timezone.utc)` — never `datetime.utcnow()` (deprecated in 3.12+).
- Store timestamps as ISO 8601 strings in SQLite, `TIMESTAMPTZ` in PostgreSQL.

## Imports
- Group imports: stdlib, then third-party, then local (`from engram.`).
- Use `TYPE_CHECKING` guards for imports needed only for type hints.
- Lazy imports inside functions are acceptable for avoiding circular dependencies.

## Conventions
- Match existing patterns — read surrounding code before introducing new ones.
- Prefer early returns over deep nesting.
- Keep lines under 100 characters.
