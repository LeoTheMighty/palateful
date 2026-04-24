<!-- refined via party-mode 2026-04-20 -->
# Epic: Activity Hub — Full History

## Overview

Today the Activity Hub is great at *current* state — the two-tab shell (shipped in `epic-activity-hub-redesign`) and the rich import-row expansion (shipped in `epic-import-row-rich-detail`) surface in-flight work clearly. But *past* state is a dead end:

- The Notifications tab fetches `?limit=50` once, filters client-side, and has no path to archived or >30d-old rows. "You're all caught up" is a wall, not a gateway.
- The Imports tab has a See-all footer, but it's hardcoded `limit=100` with no pagination. A power-user with >100 lifetime archived imports silently loses the tail.
- Empty states ("All Set" / "All clear — no imports yet") have no inline affordance to access history even when it exists.

This epic adds a symmetric See-all footer to the Notifications tab, replaces the Imports See-all's hardcoded limit with cursor-paginated lazy-loading, and turns the empty states into gateways — "See past notifications" / "See past imports" inline links appear whenever lifetime history exists.

Builds on `epic-activity-badge-integrity`. Reads the new `unread-count` payload shape. Uses `NOTIFICATION_TAB_TYPES` as the See-all type filter (same allow-list as the active list, so archived partner_actions show in See-all, archived invitations — when those ever ship — also will; old orphan `import_*` rows are gone).

## Goal

Leo opens the Activity tab, sees "All Set" on Notifications → taps the inline "See past notifications" link → scrolls through every partner_action he's ever had, in muted type, back through a year of history if he wants. Same on Imports. No "history is gone" moments. No silent truncation at row 100.

## End-User Flow

1. Leo opens the Activity tab; lands on Imports (3 actionable, from `epic-activity-badge-integrity`).
2. Scrolls past the four color sections. Sees `See all (142) ›` at the bottom. Taps it.
3. Footer expands. First page of 50 archived + >30d-completed imports renders in muted type (opacity 0.65 on onSurface). Sees date ranges like "3 months ago" on the oldest.
4. Scrolls down. Reaches the bottom of the first page. A thin progress indicator appears briefly as the next 50 load. List lengthens seamlessly.
5. Scrolls further. Reaches "That's everything. (142 total)" muted footer row. No more load attempts.
6. Swipes right on an old archived row → unarchive → 3s undo snackbar → row migrates out of See-all into its color section (or out of See-all entirely if its status is completed older than 30d — the row just disappears from See-all).
7. Switches to the Notifications tab. It shows "You're all caught up" with a subtle `See past notifications (27)` link below the illustration. Taps it.
8. Notifications See-all footer expands inline in place of the empty state (or above, if Leo had any active notifications). Paginated the same way. Leo sees partner_actions from 6 weeks ago, all muted, all read.
9. Tap any row → goes to the same detail destination as an active row (partner_action → the referenced recipe_book; an archived invitation → the accept/decline sheet in read-only mode).
10. Backs out, closes app, comes back tomorrow. The next-poll count refresh still works. No stale cache, no drift.

## Frontend Changes

**Required — heavy.** Bulk of the epic.

- **New `NotificationsSeeAllFooter` widget.** Mirrors `widgets/see_all_footer.dart` for Imports (same visual shape, same tap-to-expand-caret, same muted typography token `colorScheme.onSurface.withOpacity(0.65)`, same swipe-right-to-unarchive). Lives at `app/lib/features/activity/widgets/notifications_see_all_footer.dart`.
- **Cursor-paginated fetch on both See-all footers.** Both footers switch from a single `limit=100` fetch to a lazy-paginated scroll controller: first page on expand, next page on scroll-to-within-200px-of-end, trailing `CircularProgressIndicator` during fetch, `That's everything. (N total)` muted row when end-of-list. Uses the new backend cursor param (`?cursor=<opaque>&limit=50`).
- **See-all count provider.** A new Riverpod provider calls the lightweight count endpoint (`GET /v1/activities/see-all-count` and `GET /v1/import-items/see-all-count`) and exposes `total`. The See-all footer label reads "See all (N)" from this count — no full-list fetch needed to compute N.
- **Empty-state gateway link.** `NotificationsTab`'s empty state renders a `Text.rich` with `See past notifications (N)` as a tap target (48dp min) below the "You're all caught up" illustration, shown only when See-all count > 0. Same pattern on `ImportsTab`'s "All clear — no imports yet" with `See past imports (N)`.
- **Imports See-all pagination swap.** `see_all_footer.dart` replaces its `limit=100` call with the new cursor-paginated path. Swipe-right-to-unarchive behavior preserved.
- **Optimistic-archive reconciliation across pages.** When a user archives an active row, it optimistically moves to See-all's page-1 top. If See-all is already expanded, a soft-reload of page 1 fires; otherwise the count increments and the next expansion sees the fresh row. No cross-page invalidation needed because pagination is cursor-based, not offset-based.
- **Session-persistent expansion state.** If the user expanded See-all, switched tabs, and came back, See-all stays expanded. Same applies to Imports.
- **Pagination-safe list virtualization.** `ListView.builder` with `itemExtent` hinted where possible (rows have a near-fixed height). Memory stays bounded at ~20MB list state for 10k rows.

## Backend Changes

**Required — moderate.**

- **Cursor pagination on `GET /v1/activities`.** Accepts `cursor=<opaque>` alternative to `offset=<int>`. Cursor format: `base64url({created_at_ms}|{activity_id})`. Decode at query time; filter `created_at < <decoded_ts> OR (created_at = <decoded_ts> AND id < <decoded_id>)`. Returns `Link: <...>?cursor=<next>; rel="next"` header when more pages exist; absent header = end-of-list. Legacy `offset` still works for one release.
- **Cursor pagination on `GET /v1/import-items` and `GET /v1/import-jobs`.** Same cursor format, same semantics.
- **`include_read=<bool>` query param on `GET /v1/activities`.** Default `false` (list tab = active only). When `true`, includes read-but-not-archived rows. See-all fetch uses `include_read=true` AND `include_archived=true`.
- **`since_days=<int|null>` query param on `GET /v1/activities`.** Default `30` (current behavior). When `null`, no window — used by See-all to show truly-old rows. When `0`, empty window (useful for testing).
- **`GET /v1/activities/see-all-count`.** Returns `{archived: int, read_and_older: int, total: int}`. `archived` = `COUNT WHERE archived_at IS NOT NULL AND type IN NOTIFICATION_TAB_TYPES`. `read_and_older` = `COUNT WHERE archived_at IS NULL AND read = true AND created_at < NOW() - INTERVAL '30 days' AND type IN NOTIFICATION_TAB_TYPES`. `total = archived + read_and_older`. Sub-50ms p95 — single aggregate SQL with two filtered counts.
- **`GET /v1/import-items/see-all-count`.** Returns `{archived: int, completed_older: int, total: int}`. Same shape.
- **`list_activities.py` See-all query shape.** When the caller passes `include_archived=true AND include_read=true AND since_days=null`, returns everything archived + everything read-and-older-than-30d + everything older-than-30d (with any read state). `ORDER BY archived_at DESC NULLS LAST, created_at DESC, id DESC` for cursor stability. Note: archived_at DESC means most-recently-archived-first; NULLS LAST means non-archived-but-old rows come after archived. This matches the user expectation of "archived stuff first, then just old stuff."
- **Partial index for See-all path.** `(user_id, archived_at DESC) WHERE archived_at IS NOT NULL` already exists on `user_activities` (ahr-1) and `import_items` (ahr-1). Add a second partial index: `(user_id, created_at DESC) WHERE read = true AND archived_at IS NULL` for the read-and-older half of the Notifications See-all query. Create concurrently per the ahr-1 migration pattern.
- **Archive unarchive regression.** Existing `archive`/`unarchive` endpoints are unchanged — they still flip `archived_at`. The new See-all query just exposes the archived rows. Idempotency preserved.

## Infrastructure Changes

**None.**

- Same existing RDS indexes (plus one new partial index per table — Alembic migration). No new AWS resources. No env vars.

## Design Principles (refined via party-mode 2026-04-20)

1. **Symmetric See-all across both tabs.** Same widget shape, same position (bottom-of-list), same muted typography token. Users learn the pattern once.
2. **Pagination is cursor-based, not offset-based** — and the cursor is **multi-key row-value**, not single-key. Stored in the cursor: `(archived_at_ms_or_neg_inf, created_at_ms, id)`. WHERE clause uses Postgres row-value comparison `(COALESCE(archived_at, '-infinity'), created_at, id) < (:arch, :ts, :id)` which matches the ORDER BY exactly and survives mid-scroll archive/insert operations without skip or dup. (Single-key `created_at < :ts OR (created_at = :ts AND id < :id)` — as initially drafted — would miss rows at the archived/non-archived NULL-transition.) This is the load-bearing correctness invariant of the epic.
3. **Counts are first-class.** `see-all-count` endpoints exist specifically so the footer label doesn't require fetching rows. Sub-50ms p95 budget keeps the Activity tab snappy on expand.
4. **"All Set" is a gateway, not a wall.** Empty states carry inline links to history when history exists. When it genuinely doesn't exist (new user, lifetime count = 0), no link — pure empty state.
5. **Archived-first, then read-and-old.** See-all's ordering is `archived_at DESC NULLS LAST, created_at DESC, id DESC`. User sees "recently archived" at the top, then old-but-read items. Copy in the footer calls this "Recently archived, then older history" so users aren't confused when their all-null-archive history sorts by creation date.
6. **Swipe-right-to-unarchive in See-all.** Symmetric with the existing Imports See-all (ahr-5 AC5). 3s undo snackbar. Unarchived row migrates back to its main list.
7. **Unbounded depth.** No soft cap. The list is honest — if you had 10k imports, you can scroll all 10k. Server pagination keeps each page under 200ms.
8. **Read-and-not-archived rows stay in the active list until they fall out of the 30d window.** Then they're "read and old" — they migrate to See-all on the next refresh. This keeps the active list focused while keeping history reachable.
9. **Shared muted token lives in the design system.** `AppColors.mutedOnSurface` = `onSurface.withOpacity(0.65)`. Every See-all / history / "read-and-old" surface in the Activity Hub (and anywhere else) consumes this token; no raw `withOpacity(0.65)` calls in the new code.
10. **Virtualization correctness over hint-based optimization.** Do NOT use a fixed `itemExtent` on the Imports See-all list — rows can expand dramatically when the caret-expansion from `epic-import-row-rich-detail` is triggered, and a fixed-extent hint will clip or skip-render. Use plain `ListView.builder` (default extent auto-measured) or `itemExtentBuilder` if Flutter 3.19+ is available. Notifications See-all rows are uniform and MAY use `itemExtent` (optional optimization).
11. **Pull-to-refresh is tab-scoped.** A pull-to-refresh gesture on a tab re-fetches the active list AND refreshes the See-all count; if See-all is expanded, page 1 is re-fetched and the cursor rewinds. Subsequent pages stay cached until the user scrolls.
12. **Scroll position persists across tab switches.** Every paginated list uses a `PageStorageKey`. Switching to Notifications and back to Imports does not jump the scroll to top. Also survives the See-all collapse/expand cycle.
13. **Page-fetch failure is recoverable.** A failed page fetch (network error, 5xx, timeout ≥ 10s) renders a muted inline row: "Couldn't load more. Tap to retry." Tap re-fires the same cursor. No silent stalls.
14. **Deploy ordering is enforced in CI.** Because Epic 2 imports `NOTIFICATION_TAB_TYPES` from `libraries/utils/utils/models/user_activity.py`, a CI check asserts the constant exists before any Epic 2 code merges. This is a one-line import-check in the api test suite — prevents a cold-deploy train where Epic 2 lands before Epic 1's allow-list.

## File Structure (anticipated)

```
services/api/src/api/v1/user_activity/
├── list_activities.py                          # MODIFY — add cursor, include_read, since_days
├── see_all_count.py                            # NEW — GET /v1/activities/see-all-count
└── tests/

services/api/src/api/v1/import_job/
├── list_import_jobs.py                         # MODIFY — add cursor
├── list_import_items.py                        # MODIFY — add cursor
├── see_all_count.py                            # NEW — GET /v1/import-items/see-all-count
└── tests/

services/api/src/utils/
└── pagination.py                               # NEW or EXTEND — cursor encode/decode helpers

services/migrator/migrations/versions/
└── XXXX_add_read_and_old_partial_index.py      # NEW migration

app/lib/features/activity/
├── widgets/
│   ├── see_all_footer.dart                     # MODIFY — cursor-paginated
│   ├── notifications_see_all_footer.dart       # NEW — mirrors imports See-all
│   └── empty_state_gateway_link.dart           # NEW — inline "See past X" link
├── notifications_tab.dart                      # MODIFY — mount NotificationsSeeAllFooter + gateway
├── imports_tab.dart                            # MODIFY — mount gateway link on empty state
└── providers/
    ├── notifications_see_all_provider.dart     # NEW — paginated Riverpod provider
    ├── imports_see_all_provider.dart           # MODIFY — paginated
    └── see_all_count_provider.dart             # NEW — {archived, read_and_older, total}
```

## Story Map (refined via party-mode 2026-04-20 — afh-1 split into afh-1a + afh-1b)

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| afh-1a | Backend: multi-key cursor helper (`services/api/src/utils/pagination.py`) + cursor applied to `list_activities` (with See-all mode: `include_read`, `since_days=null`, See-all ORDER BY) | 🔴 P0 | 1 d | `epic-activity-badge-integrity` complete |
| afh-1b | Backend: cursor applied to `list_import_items` + `list_import_jobs`; concurrent-mutation invariants proved end-to-end | 🔴 P0 | 0.5 d | afh-1a |
| afh-2 | Backend: `see-all-count` endpoints + partial index migration + verify `user_activity.read` column default | 🟡 P1 | 0.5 d | afh-1a |
| afh-3 | Flutter: Notifications See-all footer + paginated provider + `PageStorageKey` + retry-on-error row + `AppColors.mutedOnSurface` token | 🔴 P0 | 1 d | afh-1a, afh-2 |
| afh-4 | Flutter: Imports See-all pagination swap (remove hardcoded `limit=100`, drop `itemExtent` on rich rows, add `PageStorageKey`, reuse retry row) | 🟡 P1 | 0.5 d | afh-1a, afh-1b |
| afh-5 | Flutter: empty-state gateway link on both tabs + pull-to-refresh wiring on both tabs | 🟡 P1 | 0.5 d | afh-3, afh-4 |
| afh-6 | Regression: end-to-end history pagination (10k rows for real virtualization test) + rapid-fire archive race + cursor concurrent-archive test + deploy-order CI guard | 🟡 P1 | 0.75 d | afh-3, afh-4, afh-5 |

**Total estimated effort: 4.75 days**

**Parallel tracks:**
- Backend track: afh-1a → afh-1b → afh-2 in series
- Frontend track: afh-3 after afh-1a + afh-2; afh-4 parallelizes with afh-3 after afh-1b; afh-5 follows; afh-6 last

---

## Story afh-1a: Backend — multi-key cursor helper + `list_activities` See-all mode

As the Activity backend,
I want a multi-key cursor helper that matches `ORDER BY archived_at DESC NULLS LAST, created_at DESC, id DESC` exactly, so pages are stable even when rows flip archived state mid-scroll,
so that Flutter's See-all footers never skip or duplicate rows during user archive/unarchive activity.

### Acceptance Criteria

1. New helper module `services/api/src/utils/pagination.py` exposes:
   - `encode_cursor(archived_at_ms: int | None, created_at_ms: int, row_id: str) -> str`
   - `decode_cursor(cursor: str) -> tuple[int | None, int, str]`
   - Format: `base64url({archived_at_ms | "-"}|{created_at_ms}|{id})` — `-` literal sentinel for NULL archived_at. Total ~68 chars.
   - Invalid cursors (malformed base64, wrong field count, non-numeric ts, etc.) → raise `InvalidCursorError` handled by FastAPI exception handler as `400 Bad Request detail="invalid_cursor"`.
2. `list_activities` accepts `?cursor=<opaque>` as an alternative to `?offset=<int>`. Both params present → `400 detail="cursor_and_offset_mutually_exclusive"`. Legacy `offset` path preserved for one release, deprecated in docstring.
3. `list_activities` accepts `include_read=<bool>` (default `false`) and `since_days=<int | null>` (default `30`). Wire-level semantics for `since_days=null`: Pydantic field typed `Optional[int] = 30`; client sends `?since_days=` (empty) to mean null, or omits the param to use default. Documented in the endpoint docstring.
4. **See-all mode = `include_archived=true AND include_read=true AND since_days=null`.** Ordering in See-all mode: `ORDER BY archived_at DESC NULLS LAST, created_at DESC, id DESC`. Default (active-list) ordering: `ORDER BY created_at DESC, id DESC`.
5. **Cursor WHERE clause in See-all mode uses row-value comparison:**
   ```sql
   WHERE (COALESCE(archived_at, '-infinity'), created_at, id)
       < (COALESCE(:arch, '-infinity'), :created_at, :id)
   ```
   with the constants supplied by `decode_cursor`. This matches the multi-key ORDER BY exactly and survives rows flipping `archived_at` mid-scroll. (Single-key `created_at < :ts OR (created_at = :ts AND id < :id)` is **forbidden** — it will skip rows at the null→non-null transition and is the P0 bug that the party-mode review caught.)
6. Default-mode cursor WHERE is `(created_at, id) < (:ts, :id)` (two-key; no archived_at dimension since the default list excludes archived rows anyway).
7. Response includes `Link: <path>?cursor=<next>; rel="next"` header when more pages exist. Header absent when end-of-list (last page OR empty page).
8. **Concurrent-mutation invariant.** Under concurrent writes, a row inserted mid-paginate does not cause a row on page N+1 to be skipped OR duplicated. Proved by two tests:
   - (a) insert mid-paginate: fetch page 1 → insert a row at a `created_at` between two pages → fetch page 2 → assert row is EITHER on page 2 OR absent from it, never both nor missing-from-both.
   - (b) **archive mid-paginate (new, from party-mode):** fetch page 1 of See-all → archive an unarchived row on page 2 via the archive endpoint → fetch page 2 → assert the archived row is either already-visible-on-page-1 (rare, since archive bumps it to top) OR present on page 2 OR on a later page, but never duplicated or missing.
9. `limit` clamped at 100. `?cursor=` requests set their own cursor-derived offset; `offset=` still works for one release.
10. Coverage stays at 100% on `services/api`. The pagination helper has unit tests for: roundtrip encode/decode; None archived_at; invalid base64; missing fields; oversized cursor.
11. `EXPLAIN ANALYZE` on a seeded 10k-row table confirms the See-all cursor query uses the `(user_id, archived_at DESC)` partial index (archived rows) and the new `(user_id, created_at DESC) WHERE read = true AND archived_at IS NULL` partial index (read-and-old rows); assertion in the test.
12. **Cursor tampering is acceptable within scope**: an unsigned cursor means a user can fabricate pagination state for their own rows. Low risk — they can only skip / re-show their own history. An HMAC is explicitly deferred to a follow-up epic if a tampering surface emerges.

### Key Files

- Create: `services/api/src/utils/pagination.py`
- Modify: `services/api/src/api/v1/user_activity/list_activities.py`
- Tests: `services/api/tests/utils/test_pagination.py`, `services/api/tests/api/v1/user_activity/test_list_activities.py`

---

## Story afh-1b: Backend — cursor on `list_import_items` + `list_import_jobs`

As the Activity backend,
I want cursor pagination on the import endpoints using the same helper from afh-1a,
so that the Imports See-all footer can scroll unbounded history.

### Acceptance Criteria

1. `list_import_items` and `list_import_jobs` accept `?cursor=<opaque>` using the same helper. `?limit` clamped at 100. Both params-both-present rule applies.
2. See-all mode on both endpoints: `?include_archived=true` AND either `?archived_only=true` OR `?status=completed AND created_at < now-30d`. ORDER BY is `archived_at DESC NULLS LAST, created_at DESC, id DESC` — same multi-key row-value WHERE as afh-1a.
3. `NOTIFICATION_TAB_TYPES` does NOT apply here (imports have `status`, not `type`).
4. Concurrent-mutation test applies: archive mid-paginate, insert mid-paginate — same invariants as afh-1a AC8.
5. `Link: rel="next"` header parity with afh-1a.
6. `EXPLAIN ANALYZE` confirms the See-all query uses `(user_id, archived_at DESC) WHERE archived_at IS NOT NULL` (existing from ahr-1) for archived rows and `(user_id, created_at DESC) WHERE archived_at IS NULL AND status = 'completed'` (new in afh-2) for the completed-older bucket.
7. Coverage stays at 100%.

### Key Files

- Modify: `services/api/src/api/v1/import_job/list_import_items.py`
- Modify: `services/api/src/api/v1/import_job/list_import_jobs.py`
- Tests: `services/api/tests/api/v1/import_job/test_list_import_items.py`, `test_list_import_jobs.py`

---

## Story afh-2: Backend — see-all-count endpoints + partial index

As the Activity backend,
I want lightweight count endpoints that return the See-all totals without fetching rows, and an index that keeps those counts fast,
so that the Flutter "See all (N)" label renders immediately on tab load without a full-list fetch.

### Acceptance Criteria

1. `GET /v1/activities/see-all-count` returns `{archived: int, read_and_older: int, total: int}`. Queries:
   - `archived` = `COUNT WHERE user_id = ? AND archived_at IS NOT NULL AND type IN NOTIFICATION_TAB_TYPES`.
   - `read_and_older` = `COUNT WHERE user_id = ? AND archived_at IS NULL AND read = true AND created_at < NOW() - INTERVAL '30 days' AND type IN NOTIFICATION_TAB_TYPES`.
   - `total = archived + read_and_older`.
2. `GET /v1/import-items/see-all-count` returns `{archived: int, read_and_old_completed: int, total: int}`. (Field renamed from initial draft's `completed_older` — the party-mode review flagged it as misleading. `read_and_old_completed` signals "not archived, just aged out.") Queries:
   - `archived` = `COUNT WHERE user_id = ? AND archived_at IS NOT NULL`.
   - `read_and_old_completed` = `COUNT WHERE user_id = ? AND archived_at IS NULL AND status = 'completed' AND created_at < NOW() - INTERVAL '30 days'`.
3. Both endpoints p95 ≤ 50ms on a table with 10k rows for the user. Proved by a perf test that seeds 10k rows + times the call.
4. **`user_activity.read` column default verification.** Pre-migration: assert the column exists with `NOT NULL DEFAULT FALSE` in the SQLAlchemy model + confirmed by a fresh Postgres introspection in the test. If the column allows NULL, the migration adds a backfill step: `UPDATE user_activities SET read = FALSE WHERE read IS NULL` followed by `ALTER COLUMN ... SET NOT NULL DEFAULT FALSE`. Prevents the `read_and_older` count from under-reporting rows where `read` was never explicitly set.
5. New Alembic migration adds a partial index on `user_activities`: `(user_id, created_at DESC) WHERE read = true AND archived_at IS NULL`. Created with `postgresql_concurrently=True` using the same `COMMIT` + `CREATE INDEX CONCURRENTLY` pattern from ahr-1. For `import_items`: existing indexes plus `(user_id, created_at DESC) WHERE archived_at IS NULL AND status = 'completed'` to keep the `read_and_old_completed` count fast.
6. Both count queries use the partial indexes — asserted with `EXPLAIN ANALYZE` in the test suite. The `created_at < NOW() - INTERVAL '30 days'` predicate runs at query time (NOT in the index WHERE, per NFR-ABI-2 — `NOW()` isn't immutable); the index covers the `read = true AND archived_at IS NULL` prefix and the planner uses it as a seek.
7. Coverage stays at 100% on `services/api`. Both new endpoints have integration tests.

### Key Files

- Create: `services/api/src/api/v1/user_activity/see_all_count.py`
- Create: `services/api/src/api/v1/import_job/see_all_count.py`
- Wire both into their respective routers
- Create: `services/migrator/migrations/versions/XXXX_add_see_all_partial_indexes.py`
- Tests: `services/api/tests/api/v1/user_activity/test_see_all_count.py`, `services/api/tests/api/v1/import_job/test_see_all_count.py`

---

## Story afh-3: Flutter — Notifications See-all footer + paginated provider

As Leo,
I want a "See all" button at the bottom of the Notifications tab that reveals every archived and old-and-read notification I've ever had,
so that history is reachable, not gone.

### Acceptance Criteria

1. New `NotificationsSeeAllFooter` widget at `app/lib/features/activity/widgets/notifications_see_all_footer.dart`. Mirrors the shape of the existing `SeeAllFooter` (Imports): collapsed single-row "See all (N) ›", expanded list in muted type via the new shared token `AppColors.mutedOnSurface`.
2. **New shared token** `AppColors.mutedOnSurface = onSurface.withOpacity(0.65)` added to `app/lib/theme/app_colors.dart` (or equivalent). Both the new `NotificationsSeeAllFooter` and the existing `SeeAllFooter` (Imports, modified in afh-4) consume this token — no raw `withOpacity(0.65)` calls in either file.
3. Count label uses the new `see-all-count` endpoint via a `NotificationsSeeAllCountProvider`. Re-polled on tab visible every 30s; refreshed optimistically after archive/unarchive.
4. Expanded list fetches cursor-paginated pages of 50 rows each via `GET /v1/activities?include_archived=true&include_read=true&since_days=&limit=50&cursor=...` (empty `since_days=` = null-sentinel per afh-1a AC3).
5. Scroll controller detects within-200px-of-end → fires next-page fetch. Trailing `CircularProgressIndicator` renders during fetch. End-of-list → muted "That's everything. (N total)" row.
6. **Retry-on-failure row.** If a page fetch fails (network error, 5xx, timeout ≥ 10s), render a muted inline row with "Couldn't load more. Tap to retry." instead of the spinner. Tap re-fires the same cursor. A subsequent successful fetch replaces the row with the retrieved items.
7. Tap on a row → same destination as an active notification (partner_action → referenced recipe_book, etc.). Muted typography does not prevent interaction.
8. Swipe-right unarchives: calls `POST /v1/user-activities/{id}/unarchive`, optimistic removal with 3s undo snackbar, fires unarchive on timeout expiration. Matches Imports See-all behavior (ahr-5 AC5).
9. If `total == 0`, the footer is not rendered (no "See all (0) ›" ghost row).
10. **Session-persistent state.** Two pieces: (a) expansion bool held in a `StateProvider<bool>` scoped to the Notifications tab; (b) **scroll offset preserved via `PageStorageKey('notifications-see-all-list')`**. Switching to Imports and back, or collapse/expand, both land the list at its last scroll position — not the top.
11. **Virtualization.** Plain `ListView.builder` (no fixed `itemExtent` — Notification rows are short and near-uniform but not *guaranteed* uniform; default auto-measure is safe). For the memory-bound guarantee, the test harness seeds 10k archived rows, paginates to end, and asserts DevTools memory stays under 20MB list-related.
12. Widget test: pump `NotificationsTab` with stub count `{total: 142}`; assert footer reads "See all (142) ›". Tap it. Fetch stub returns 50 rows. Assert 50 rows rendered. Scroll to within 200px of end. Fetch stub returns 50 more. Assert 100 rows rendered. Fetch returns empty list. Assert "That's everything. (142 total)" rendered.
13. Retry-test: stub fetch to fail on page 2 with a 500 → assert "Couldn't load more. Tap to retry." row appears. Tap. Re-fetch succeeds. Assert page 2 rows render.
14. Scroll-persistence test: pump, expand, scroll halfway, switch to Imports, switch back. Assert scroll offset preserved.

### Key Files

- Create: `app/lib/features/activity/widgets/notifications_see_all_footer.dart`
- Create: `app/lib/features/activity/providers/notifications_see_all_provider.dart`
- Create: `app/lib/features/activity/providers/see_all_count_provider.dart`
- Modify: `app/lib/features/activity/notifications_tab.dart` (mount the footer)
- Tests: `app/test/features/activity/widgets/notifications_see_all_footer_test.dart`

---

## Story afh-4: Flutter — Imports See-all pagination swap

As Leo,
I want the Imports See-all to scroll past 100 items without silently cutting me off,
so that my long-term import history is all there.

### Acceptance Criteria

1. `see_all_footer.dart` drops the hardcoded `limit=100` on its single fetch. Replaces with a paginated scroll controller matching the Notifications See-all shape (Story afh-3).
2. Count label uses `GET /v1/import-items/see-all-count` via a new `ImportsSeeAllCountProvider` (sibling to `NotificationsSeeAllCountProvider`). Count field names updated to `{archived, read_and_old_completed, total}` to match afh-2 AC2.
3. Pagination: 50 per page, cursor-based. Trailing progress indicator on fetch. "That's everything. (N total)" muted row at end. Retry-on-failure row from afh-3 AC6 reused verbatim.
4. **`itemExtent` removed from the Imports See-all list.** Imports rows support the caret-expansion from `epic-import-row-rich-detail` (stage timeline, confidence, raw parse preview) which changes row height dramatically — a fixed `itemExtent` hint would clip or skip-render expanded rows. Use plain `ListView.builder` (default auto-measure) or `itemExtentBuilder` (Flutter 3.19+) if profiling shows a win. Row height variance is expected; virtualization still works via the builder pattern.
5. Swipe-right-to-unarchive behavior preserved (ahr-5 AC5). Optimistic row removal + 3s undo.
6. `PageStorageKey('imports-see-all-list')` preserves scroll offset across tab switches and collapse/expand cycles. Mirrors afh-3 AC10.
7. `AppColors.mutedOnSurface` token consumed (no raw `withOpacity(0.65)` left in this file).
8. No regression on the existing See-all ordering: archived first by archive date, then >30d-completed by created_at.
9. Widget test: pump with stub count `{total: 250}`; assert footer reads "See all (250) ›"; expand; fetch 50; scroll; fetch next 50; repeat to end-of-list; assert final "That's everything. (250 total)" row and that scroll didn't stall.
10. Regression test: seed 1 archived yellow item → expand See-all → swipe-right → assert row moves to Needs Review section; tap undo within 3s → assert row returns to See-all. Matches ahr-5 AC10.
11. Caret-expand regression: seed a See-all row with telemetry; expand the caret; assert the rich detail renders and the list does not skip rows below the expanded one (proves no `itemExtent` regression).

### Key Files

- Modify: `app/lib/features/activity/widgets/see_all_footer.dart`
- Modify: `app/lib/features/activity/providers/imports_see_all_provider.dart` (or create if it was inline today)
- Use: `app/lib/features/activity/providers/see_all_count_provider.dart` (from afh-3)
- Tests: `app/test/features/activity/widgets/see_all_footer_test.dart` (extended)

---

## Story afh-5: Flutter — empty-state gateway links

As Leo,
I want "See past notifications" / "See past imports" links in the empty states when I actually have history,
so that "All Set" doesn't feel like a dead end.

### Acceptance Criteria

1. New `EmptyStateGatewayLink` widget takes `count: int`, `label: String`, `onTap: VoidCallback`. Renders nothing when `count == 0`; otherwise renders a centered `Text.rich` with `label` + small ` (N)` suffix inside an `InkWell` + 48dp padding. **Trailing chevron-down glyph + underline + slightly-higher-contrast color on the link text** explicitly signal "this expands inline" (not "this navigates away") — avoids the ambiguity the party-mode review flagged.
2. `NotificationsTab` empty state ("You're all caught up") renders the gateway link below the illustration when `see_all_count.total > 0`. Label: `See past notifications`. Tap → expands `NotificationsSeeAllFooter` AND auto-scrolls to it (no manual scroll-down required after tap).
3. `ImportsTab` empty state ("All clear — no imports yet") renders the gateway link below the illustration when `see_all_count.total > 0`. Label: `See past imports`. Tap → expands `SeeAllFooter` AND auto-scrolls to it.
4. When `total == 0` (brand-new user, zero lifetime history), the link is absent. Pure empty state.
5. First-run variant on Imports (from ahr-4 AC5): the existing first-run card is preserved; the gateway link is mutually exclusive (first-run shows → no gateway link since `total == 0`).
6. **Pull-to-refresh wired on both tabs.** A `RefreshIndicator` wraps the active list on each tab body. Gesture triggers: (a) re-fetch of the active list, (b) re-fetch of the `see_all_count`, (c) if See-all is currently expanded, reset its cursor and re-fetch page 1. Subsequent pages remain cached until the user scrolls.
7. A11y: `Semantics` label reads "See past notifications, N items, tap to expand". Keyboard-focusable. The chevron-down is part of the label, not a separate semantic node.
8. Widget test: pump `NotificationsTab` with empty active list + stub count `{total: 27}`. Assert "See past notifications" link renders. Tap it. Assert See-all footer is expanded AND the scroll view has auto-scrolled so the footer is visible.
9. Widget test: pump with `{total: 0}`. Assert no gateway link. Pure empty state.
10. Pull-to-refresh test: pump with 3 active rows + expanded See-all; swipe down on tab body; assert all three fetches fire (active list, count, See-all page 1).

### Key Files

- Create: `app/lib/features/activity/widgets/empty_state_gateway_link.dart`
- Modify: `app/lib/features/activity/notifications_tab.dart`
- Modify: `app/lib/features/activity/imports_tab.dart`
- Tests: `app/test/features/activity/widgets/empty_state_gateway_link_test.dart`, updated tab tests

---

## Story afh-6: Regression — full history end-to-end + memory

As Leo,
I want proof that the full-history flow doesn't regress the badge / tab / archive behavior shipped earlier,
so that polish doesn't quietly break production.

### Acceptance Criteria

1. Integration test: seed **10_000 archived partner_actions** + 200 read-and-older partner_actions + 3 active partner_actions + 50 actionable imports + **10_000 archived imports**. Seed sizes elevated from the draft's 500/400 to genuinely stress virtualization — the draft's original seeds did not actually exercise `ListView.builder` memory behavior. Cold-start app. Assert:
   - Bottom-nav badge reads `53` (3 + 50).
   - Notifications tab renders 3 active rows + "See all (10200) ›" footer.
   - Imports tab renders 50 actionable rows across 4 sections + "See all (10000) ›" footer.
2. **Virtualization memory test.** Expand Notifications See-all. Scroll to bottom (204 pages at 50/page). Assert DevTools memory snapshot stays under 20MB of list-related allocations (measured via `Memory.vm.fullGc()` + list-class-filtered heap stats). Assert no row is lost or duplicated across the full scroll. Same test on Imports See-all with 10k archived rows.
3. **Cursor concurrent-archive test (new, from party-mode).** During Notifications See-all pagination, archive a row that is on page N+1 via the archive endpoint between the fetches of page N and N+1. Assert the archived row is either already-visible-on-an-earlier-page OR present-on-its-original-page-position OR on a later page — but never duplicated and never missing. Repeat on Imports See-all.
4. **Rapid-fire archive race (new, from party-mode).** Seed 1 active partner_action. Swipe-archive, immediately swipe-unarchive (within 3s undo), immediately swipe-archive again. Assert final state: row archived, bottom-nav count stable, See-all count bumps by exactly 1, no duplicate in See-all, no ghost undo snackbar lingering.
5. Archive one active partner_action. Bottom-nav drops to `52`. See-all count increments to `10201`. Next expansion (or live-updated cached list) shows the newly-archived row at the top of See-all.
6. Unarchive an old archived row from See-all. See-all count drops to `10200`. Notifications active list shows the restored row. Bottom-nav returns to `53`.
7. Switch to Imports tab. Expand See-all. Paginate to the end. Assert no row lost, no duplicate. Concurrent-insert test: during pagination, insert 2 new archived imports; assert the next pull-to-refresh or scroll-to-top exposes them correctly (top of See-all).
8. Push-dispatch regression (from abi-2a AC3): a new needs-review import still triggers an FCM push. Bottom-nav bumps from `53` to `54` on next poll.
9. Empty-state gateway regression: stub count to `0`; assert no gateway link on either tab. Stub to `1`; assert link renders (with chevron-down glyph). Tap → See-all expands AND auto-scrolls into view.
10. Pull-to-refresh regression: on an active+expanded state, pull-to-refresh fires all three fetches (active, count, See-all page 1); assert visible rows match.
11. Retry-on-failure regression: stub page N fetch to 500; assert "Couldn't load more. Tap to retry." row. Tap; stub succeeds; assert rows render.
12. Scroll-persistence regression: expand See-all, scroll halfway, switch tabs, switch back; assert scroll offset preserved via `PageStorageKey`.
13. **Deploy-order CI guard test.** Add a test that imports `NOTIFICATION_TAB_TYPES` from `libraries/utils/utils/models/user_activity.py` and asserts it's a non-empty tuple. If Epic 2 code ever ships to CI before Epic 1 lands, this test fails at import — no green merge.
14. A11y regression: run `accessibilityGuideline` test on both tabs in expanded-See-all state. No violations. Gateway-link `Semantics` label includes "tap to expand".

### Key Files

- Tests: `app/integration_test/features/activity/full_history_flow_test.dart` (new)
- Tests: `services/api/tests/integration/test_full_history_pagination.py` (backend-side cursor stability under concurrent writes)

---

## Dependencies

- **Hard dependency on `epic-activity-badge-integrity`:** reads the `NOTIFICATION_TAB_TYPES` allow-list; assumes the orphan `import_*` user_activity rows are already gone (otherwise See-all would expose them as historical pollution).
- **Soft dependency on `bugs-act-2a-backend-fields-addendum`** (backlog, irrelevant to scope): if the stage/retry fields add more visible row states, See-all should still paginate them correctly — cursor is status-agnostic so this should Just Work.

## Open Questions for the User

None blocking. Three candidates that could come up in party-mode (Phase 6):

- Should See-all have a "clear all archived" bulk action? (Default: no — archiving is the user's "hide" mechanism; deletion isn't exposed per the non-goal in the PRD.)
- Should pull-to-refresh on a tab also refresh See-all if expanded? (Default: yes — RefreshIndicator on the whole tab scroll view.)
- Should the See-all pagination page size be configurable (50 vs 25)? (Default: 50 fixed — simpler, good enough for p95.)

## Definition of Done (Epic Level)

- Notifications tab has a See-all footer with paginated history, muted typography, swipe-right-to-unarchive.
- Imports tab See-all is cursor-paginated (not capped at 100), lazy-loads on scroll, "That's everything. (N total)" at end.
- Empty states on both tabs carry a "See past …" inline link whenever lifetime history exists.
- `GET /v1/activities` supports `cursor`, `include_read`, `since_days=null` for full-history view.
- `GET /v1/activities/see-all-count` and `GET /v1/import-items/see-all-count` return the triple under 50ms p95.
- Cursor pagination is stable under concurrent writes (no skip, no dup).
- 100% coverage on `services/api`. New Flutter tests cover the footer widget, gateway link, and pagination boundary.
- Memory test: 10k archived rows in See-all stays under 20MB client list-state.
- No regression on badge integrity (from `epic-activity-badge-integrity`), tab shell, swipe rules, or push dispatch.
