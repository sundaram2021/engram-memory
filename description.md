# What bugs were fixed and why

## Duplicate conflict cards on the dashboard

Conflicts are now normalized by fact pair before insertion with the key:

- `(min(fact_id_a, fact_id_b), max(fact_id_a, fact_id_b))`

Both SQLite and PostgreSQL now enforce that normalized pair as a unique index, and the storage/API insert paths now check for an existing pair before inserting. This prevents race conditions and repeated scans from creating multiple dashboard cards for the same underlying contradiction.

## Dismissed conflicts reappearing on refresh

Dismissed conflict IDs are now persisted in a new `dismissed_conflicts` table. Dashboard-facing conflict queries and refresh flows filter out any conflict whose ID is present there, and dismissal writes now update both the conflict row and the persistent dismissal record. This prevents a just-dismissed card from being surfaced again by a near-simultaneous refresh or background detection pass.

# What new feature was added and how it works

## Git pre-commit conflict hook

`engram install` now writes a Git hook to `.git/hooks/pre-commit` when run inside a Git repository. The hook runs:

- `engram pre-commit-hook`

That command:

1. Reads workspace credentials from the project’s `.engram.env`
2. Calls the Engram API at `/api/conflicts?status=open`
3. Prints unresolved conflicts in a terminal-friendly format if any exist
4. Exits with code `1` when unresolved conflicts exist, which blocks the commit
5. Exits with code `0` when no unresolved conflicts exist

# Which GitHub issues each change addresses

- `#266`: duplicate dashboard conflict cards are prevented by normalized-pair deduplication and a database-level unique constraint
- `#265`: dismissed conflicts stay hidden because dismissal state is persisted and filtered out during refresh/display
- `#264`: related dashboard conflict-state regressions are covered by the same conflict card deduplication and dismissal hardening
- `#239`: added the installable Git pre-commit conflict hook

# How to test each fix

## Duplicate conflict cards

- Run `python3 -m pytest tests/test_storage.py -k duplicate_conflict_pair_is_inserted_once`
- Or manually insert the same conflict pair twice in opposite orders and confirm only one conflict row/card exists

## Dismissed conflicts staying hidden

- Run `python3 -m pytest tests/test_conflicts.py -k dismissed_conflict_stays_hidden_after_refresh`
- Or create a conflict, dismiss it, trigger a dashboard refresh or conflict scan, and confirm the card does not come back

## Pre-commit hook

- Run `python3 -m pytest tests/test_cli_commit_check.py -k pre_commit_hook`
- Run `python3 -m pytest tests/test_cli_install.py -k git_pre_commit_hook`
- Or run `engram install` inside a Git repo, confirm `.git/hooks/pre-commit` exists, then run `engram pre-commit-hook`
  against a workspace with and without open conflicts to verify exit codes `1` and `0`
