# Clean Code Rules

## General Principles
1. Continuously improve and clean existing code.
2. Eliminate code duplication.
3. Define variables and functions close to their usage.

## Naming
4. Use intention-revealing names for all identifiers.
5. Name functions using verbs or verb phrases (`detect_conflicts`, `insert_fact`).
6. Name classes and modules using nouns (`EngramEngine`, `SQLiteStorage`).
7. Avoid noise words like `Info`, `Data`, `Manager` unless they carry real meaning.
8. Match name length to scope — short names for tight loops, descriptive names for module-level.

## Functions
9. Keep functions small and focused on one task.
10. Keep argument count small (0–3 preferred). Use `dict` or dataclass for groups of related params.
11. Prefer early returns over deep nesting.
12. Remove functions that are never called.
13. Break complex calculations into well-named intermediate variables.

## Modules and Classes
14. Keep classes small with one reason to change (SRP).
15. Keep internal helpers private (prefix with `_`).
16. Expose minimal surface area at module boundaries.
17. Separate business logic from error handling.

## Comments
18. Use comments only for non-obvious technical decisions.
19. Update or remove stale comments immediately.
20. Never comment out code — delete it.

## Error Handling
21. Raise exceptions with enough context to identify the source.
22. Separate normal flow from error handling paths.
23. Avoid returning `None` to signal errors — raise instead.
