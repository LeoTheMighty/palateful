# Story afh-1b: Backend — cursor on `list_import_items` + `list_import_jobs`

Status: done

## Summary

Adds cursor pagination to the two import-list endpoints using the afh-1a
helper. See-all mode (`include_archived=true` on import_items, either
`include_archived=true` or `archived_only=true` on import_jobs) uses the
3-key row-value WHERE + ORDER BY; default mode uses 2-key `(created_at,
id) < (…)`.

## What shipped

- `list_import_items.py`:
  - `?cursor` mutually exclusive with `?offset` (400
    `cursor_and_offset_mutually_exclusive`).
  - Invalid cursor → 400 `invalid_cursor`.
  - Response gains `next_cursor`. `Link: </v1/import-jobs/{job_id}/items?…; rel="next"`
    header when more pages exist.
  - See-all mode ordering: `COALESCE(archived_at,'-infinity') DESC,
    created_at DESC, id DESC`.
  - Cursor-mode ordering (not See-all): `created_at DESC, id DESC`.
  - Default (no cursor, no include_archived): legacy `ORDER BY
    created_at` ASC preserved for one release so existing offset-paginated
    clients don't regress.
  - Limit clamped at 100.
  - `total` skipped on the cursor path (heavy COUNT).
- `list_import_jobs.py`: same shape. See-all mode triggered by either
  `include_archived=true` or `archived_only=true`. Link header points at
  `/v1/import-jobs?cursor=…`.
- `import_router.py`: wires the new `cursor` query param on both
  endpoints.
- Tests: new `TestListImportItemsCursor` + `TestListImportJobsCursor`
  classes in `test_import.py` — cursor+offset 400, invalid cursor 400,
  default-mode cursor decode, see-all with archived_at value, see-all
  with null archived_at, next_cursor + Link header, see-all cursor
  encodes archived_at.

## ACs satisfied

AC1 — cursor + limit clamp + both-present rule.
AC2 — See-all mode ORDER BY + 3-key row-value WHERE.
AC3 — NOTIFICATION_TAB_TYPES doesn't apply here (imports use
`status`, not `type`). Confirmed.
AC4 — concurrent-mutation invariant: designed into the WHERE; real-DB
proof deferred to afh-6 regression tests.
AC5 — `Link: rel="next"` header parity with afh-1a.
AC6 — EXPLAIN ANALYZE deferred until afh-2 lands the second partial
index (`(user_id, created_at DESC) WHERE archived_at IS NULL AND status
= 'completed'`).
AC7 — 100% coverage on my new code in `list_import_items.py`,
`list_import_jobs.py`, and `import_router.py` (a pre-existing
`_extract_inferred_fields` branch in list_import_items.py that belongs
to efi-4 is not covered by my tests — that's a separate story).

## Files

- MODIFIED: `services/api/src/api/v1/import_job/list_import_items.py`
- MODIFIED: `services/api/src/api/v1/import_job/list_import_jobs.py`
- MODIFIED: `services/api/src/routers/v1/import_router.py`
- MODIFIED: `services/api/tests/test_import.py`

## CI

- `npx nx run api:lint` ✓
- `npx nx run api:test` ✓ (2084 passed)
