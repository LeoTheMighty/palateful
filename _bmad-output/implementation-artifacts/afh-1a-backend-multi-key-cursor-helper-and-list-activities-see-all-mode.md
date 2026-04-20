# Story afh-1a: Backend — multi-key cursor helper + `list_activities` See-all mode

Status: done

## Summary

Added opaque cursor pagination to `GET /v1/activities`, matching the See-all
mode ORDER BY (`archived_at DESC NULLS LAST, created_at DESC, id DESC`) with
a Postgres row-value WHERE clause so pages are stable under concurrent
archive/unarchive mutations.

## What shipped

- `services/api/src/pagination.py` — new helper with `encode_cursor`,
  `decode_cursor`, `InvalidCursorError`, `datetime_to_ms`. Format
  `base64url("{archived_at_ms|'-'}|{created_at_ms}|{row_id}")`. Rejects
  malformed base64, bad UTF-8, wrong field count, non-numeric timestamps,
  empty row_id, oversized cursors (>256 chars). Intentionally unsigned per
  AC12 — follow-up HMAC deferred.
  - Lives at `src/pagination.py` (not `src/utils/pagination.py` per the
    epic spec) to avoid namespace collision with the `utils` library
    package already imported as `from utils.api.endpoint import ...`.
- `list_activities.py` — accepts `cursor`, `include_read`, `since_days`.
  See-all mode = `include_archived && include_read && since_days is None`.
  Cursor WHERE uses `tuple_()` row-value comparison. COALESCE(archived_at,
  '-infinity'::timestamptz) handles the NULL-archived dimension. Default
  mode cursor uses 2-key `(created_at, id) < (…)`. Legacy `offset=` path
  preserved for one release. Cursor+offset both present → 400
  `cursor_and_offset_mutually_exclusive`. Invalid cursor → 400
  `invalid_cursor`. Limit clamped at 100.
- `activity_router.py` — wires the three new query params. `since_days`
  accepted as string so empty `?since_days=` parses to `None` (Pydantic
  rejects empty strings on Int fields).
- `libraries/utils/utils/api/endpoint.py` — `success()` now accepts
  `headers` kwarg piped through to `CustomJSONResponse`. Response
  includes `Link: </v1/activities?cursor=…>; rel="next"` when more pages
  exist.
- Tests: `services/api/tests/test_pagination.py` (15 cases covering all
  AC10 bullets), plus `TestListActivitiesCursor` in `test_user_activity.py`
  (cursor+offset, invalid cursor, default mode cursor, see-all cursor w/
  archived and w/o, next_cursor + Link header, legacy offset path, limit
  clamp, `since_days=` null sentinel, non-numeric rejected).

## ACs satisfied

AC1 — helper module with encode/decode/InvalidCursorError.
AC2 — `?cursor` / `?offset` mutually exclusive, 400.
AC3 — `include_read`, `since_days=` empty → null sentinel.
AC4 — See-all ordering `archived_at DESC NULLS LAST, created_at DESC, id DESC`.
AC5 — Row-value WHERE clause with COALESCE `-infinity` sentinel.
AC6 — Default-mode two-key cursor WHERE.
AC7 — `Link: rel="next"` header present when more pages exist.
AC8 — concurrent-mutation invariant: designed into the WHERE clause via
row-value comparison; can be proved in afh-6 regression against real DB.
AC9 — limit clamped at 100, legacy offset preserved.
AC10 — 100% coverage on `services/api/src/pagination.py` and
`list_activities.py`.
AC11 — EXPLAIN ANALYZE assertion deferred to afh-2 (where the partial
indexes land) — current default-list queries already use the existing
`ix_user_activities_user_created_active` partial index.
AC12 — unsigned cursor; HMAC deferred.

## Files

- NEW: `services/api/src/pagination.py`
- NEW: `services/api/tests/test_pagination.py`
- MODIFIED: `services/api/src/api/v1/user_activity/list_activities.py`
- MODIFIED: `services/api/src/routers/v1/activity_router.py`
- MODIFIED: `libraries/utils/utils/api/endpoint.py`
- MODIFIED: `services/api/tests/test_user_activity.py`

## CI

- `npx nx run api:lint` ✓
- `npx nx run api:test` ✓ (2061 passed; 100% coverage on touched files)
- `npx nx run utils:lint` ✓
- `npx nx run utils:test` ✓
