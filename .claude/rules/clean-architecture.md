# Architecture Rules

Engram uses a flat module structure under `src/engram/`. There are no nested layers — each module has a clear responsibility.

## Module Boundaries
1. **Storage layer** (`storage.py`, `postgres_storage.py`) — All database I/O goes through `BaseStorage` ABC. Never write raw SQL outside these files.
2. **Engine** (`engine.py`) — Core logic: commit pipeline, conflict detection. Receives storage via constructor injection. Does not import server or CLI code.
3. **I/O layer** (`server.py`, `rest.py`, `cli.py`, `dashboard.py`) — Entry points. These depend on engine and storage, never the reverse.
4. **Utilities** (`embeddings.py`, `entities.py`, `secrets.py`, `suggester.py`) — Stateless helpers called by the engine or server.

## Key Patterns
1. **Abstract base class for storage** — `BaseStorage` defines the contract with `@abstractmethod`. `SQLiteStorage` and `PostgresStorage` implement it. Add new backends by subclassing `BaseStorage`.
2. **Constructor injection** — `EngramEngine(storage: BaseStorage)`. Engine never creates its own storage instance.
3. **Data as plain dicts** — Facts, conflicts, and agents are `dict[str, Any]` throughout. No Pydantic models or dataclasses.
4. **Async everywhere** — All storage and engine methods are `async def`. Never introduce synchronous I/O.
5. **Background detection** — Conflict detection runs as an async worker, not inline with commits.

## Rules
- Do not introduce circular imports. Use `TYPE_CHECKING` guards for type-only references.
- New storage methods must be added to `BaseStorage` first, then implemented in both backends.
- Keep the module boundary clean — server/CLI should not reach into storage internals, only through engine.
