# Story abi-2b: Backend — soft-archive orphan `import_*` user_activity rows

Status: ready-for-dev

## Story

As the Activity backend,
I want existing orphan `import_*` user_activity rows to become invisible to the UI and count queries without being hard-deleted,
so that a rollback path exists if any downstream consumer surfaces after ship.

## Acceptance Criteria

1. New Alembic migration `abi2bsoftarch1` chained off `abi1iiact01`:
   - Pre-UPDATE row count logged.
   - If count > 100_000 → abort migration with a clear RuntimeError.
   - `UPDATE user_activities SET archived_at = NOW() WHERE type IN ('import_started','import_complete','import_needs_review','import_failed') AND archived_at IS NULL`.
   - Write an audit error_logs row post-UPDATE: `service="audit"`, `error_type="SoftArchiveOrphanActivities"`, `error_message` with affected row count + types.
2. Rollback path: `downgrade()` documents a single UPDATE to unset `archived_at` on rows archived within a deploy window — downgrade body itself does NOT un-archive automatically (rollback is a manual data-fix, not an automatic reverse migration).
3. Migration runs in a single transaction — no `CONCURRENTLY`. `UPDATE` against the indexed `type` column is fast.
4. Does NOT use `CASCADE`.
5. Idempotent: re-running the migration after soft-archive is a no-op (row count is 0 post-archive).

## Key Files

- Create: `services/migrator/migrations/versions/20260420010000_soft_archive_orphan_import_user_activities.py`

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### File List
