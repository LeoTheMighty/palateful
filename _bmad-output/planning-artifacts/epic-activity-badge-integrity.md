<!-- refined via party-mode 2026-04-20 -->
# Epic: Activity Hub — Badge Integrity

## Overview

The bottom-nav Activity badge shows a number that doesn't match what the user can see. Concrete root causes (audited 2026-04-20):

1. `GET /v1/activities/unread-count` (`services/api/src/api/v1/user_activity/unread_count.py:15-23`) has no `type` filter and no 30-day window, so it counts every unread, non-archived row: `import_started`, `import_complete`, `import_needs_review`, `import_failed`, `partner_action`. The Notifications tab client-side filters to `{invitation, partner_action, meal_reminder}` (two of which are never created). Badge says N; Notifications list shows ≪N.
2. Flutter's `importsActionableBadgeProvider` (under `app/lib/features/activity/providers/`) computes the imports-side actionable count correctly but is never read — the "ahr-7 wires the bottom-nav end" comment in-code admits this was left unfinished.
3. Several write sites (`start_import.py`, `create_recipe_task.py`, `match_ingredients_task.py`, `extract_recipe_task.py`, `sweep_stuck_imports.py`) insert `import_*` user_activity rows whose only purpose today is driving push notifications. Those rows bump the bell count but aren't surfaced in the Notifications tab.

This epic fixes all three at the source. One combined bell number (unread notifications + actionable imports), a locked server-side allow-list of `user_activity.type` values the Notifications tab shows, and removal of the parallel `import_*` user_activity writes that push-dispatch doesn't read. Ships first; unblocks `epic-activity-full-history`.

## Goal

Open the app, look at the bottom nav: the Activity badge number is the exact sum of items the user could act on right now. Tap the tab, land on whichever side has more (notifications or imports), and every badge number agrees with every other badge number — bottom-nav, Notifications tab, Imports tab — always.

## End-User Flow

1. Leo opens the app. Bell badge reads `5` — a mix of 2 needs-review imports, 1 failed import, and 2 unread partner-action notifications.
2. Taps the Activity tab. The Imports tab opens by default (3 actionable imports > 2 unread notifications). Imports tab badge reads `3`; Notifications tab badge reads `2`; bottom-nav still reads `5`.
3. Swipes one failed import to archive. Optimistic removal; bottom-nav badge drops to `4` within the optimistic window; Imports tab badge drops to `2`; next poll confirms.
4. Opens the Notifications tab; Notifications badge drops to `0` (mark-all-read fires on tab open, unchanged behavior); bottom-nav now reads `2` (imports actionable only).
5. A new partner_action arrives via push → server count for notifications increments → next 30s poll on the bottom-nav refreshes → badge reads `3` (2 imports + 1 new notification).
6. Leo backgrounds the app, comes back 30min later. No drift — badge still reads the true actionable count. No ghost increments from import_started/import_complete rows.

## Frontend Changes

**Required — moderate.**

- **`unread-count` response-shape migration.** `ActivityReadProvider` (or a new `ActivityBadgeProvider`) parses the new payload `{notifications: int, imports_actionable: int}` and exposes both. Old `{count: int}` path kept for one release behind a capability check — if the new keys are missing, fall back to the single-count field.
- **Bottom-nav badge formula.** `scaffold_with_bottom_nav.dart:64-66` reads the sum. One number displayed. If `imports_actionable > 0` and `notifications == 0`, badge color stays the current accent; no color swap based on source.
- **Bottom-nav tap destination.** New helper in `activity_tab_provider.dart`: `_initialTabFromCounts(notifications: int, imports: int)` returns `ActivityTab.imports` if `imports > notifications`, else `ActivityTab.notifications`. Called only when the route is opened without `?tab=` — push-payload deep-links with explicit `?tab=` continue to win.
- **Orphan provider cleanup.** `importsActionableBadgeProvider` is either wired into the bottom-nav formula (preferred — single source of truth) or deleted. No dead code left.
- **Imports tab badge.** The in-tab badge stays; formula unchanged (actionable imports = in-progress + needs-review + failed). This epic guarantees the tab badge matches the `imports_actionable` field of the new payload.
- **Notifications tab badge.** The in-tab badge stays; formula = `notifications` field of the new payload. Mark-all-read on tab open still drops it to 0 and still fires `/v1/activities/read-all`.

## Backend Changes

**Required — larger.**

- **`GET /v1/activities/unread-count` returns structured payload.** New shape: `{notifications: int, imports_actionable: int, count: int}`. `count` stays for one release as `notifications + imports_actionable` for backward compatibility.
- **`notifications` computation.** Filters: `user_id = me`, `read = false`, `archived_at IS NULL`, `type IN NOTIFICATION_TAB_TYPES`, `created_at >= NOW() - INTERVAL '30 days'`. This mirrors the window and filter of the `list_activities` endpoint exactly.
- **`imports_actionable` computation.** Filters: `user_id = me`, `archived_at IS NULL`, `dismissed_at IS NULL`, `status IN ('pending','processing','extracting','matching','awaiting_parser','awaiting_review','failed')`. Distinct import_items (not jobs). Green (`completed + created_recipe_id IS NOT NULL`) explicitly excluded.
- **`NOTIFICATION_TAB_TYPES` allow-list constant.** Lives in `libraries/utils/utils/models/user_activity.py`. Current membership: `['partner_action']`. A thin module-level export. Both `unread_count.py` and `list_activities.py` import from here — single source of truth.
- **`list_activities.py` type filter.** Stops returning `import_*` types by default. A new `?include_system_types=true` query param restores the old behavior for admin/debugging.
- **Dead-write removal.** Audit every `create_activity()` call site that creates an `import_*` type row. For each: confirm whether push-dispatch reads the row (it doesn't — push_notifications service reads the import_item directly). Delete the `create_activity` call. Audit trail: each deletion gets a commit message + a note in the epic retro.
  - `services/api/src/api/v1/import_job/start_import.py:431` — `import_started` — DELETE
  - `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py:342` — `import_complete` — DELETE
  - `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py:149` — `import_needs_review` — DELETE
  - `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` — `import_failed` — DELETE
  - `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports.py` — `import_failed` — DELETE
- **Two-phase cleanup migration (refined via party-mode).** A single-shot hard DELETE was deemed risky — if any downstream consumer we missed breaks, rows are gone. Instead:
  - **Phase A (this epic, story abi-2b):** `UPDATE user_activities SET archived_at = NOW() WHERE type IN ('import_started','import_complete','import_needs_review','import_failed') AND archived_at IS NULL`. Rows become invisible to UI and count queries (both filter on `archived_at IS NULL`); the rows still exist in DB for rollback. Pre-migration safety rail: `SELECT COUNT(*)` logged first; abort if > 100k rows (forces a human decision).
  - **Phase B (follow-up epic, one release after Epic 2 ships):** `DELETE FROM user_activities WHERE type IN (...) AND archived_at IS NOT NULL`. Out of scope here — tracked as a placeholder entry in sprint-status.yaml.

## Infrastructure Changes

**None.**

- No new AWS resources, no env vars, no Terraform. Single migration to clear dead rows + no-schema-change endpoint refactor.

## Design Principles (refined via party-mode 2026-04-20)

1. **One number in the bell. One formula. Pure sum.** `bell = notifications + imports_actionable`. No weighting, no priority. Green is never in the count.
2. **Single source of truth for "what counts as a notification."** `NOTIFICATION_TAB_TYPES` constant at `libraries/utils/utils/models/user_activity.py` (not `services/api/src/constants.py` — the utils path keeps it importable from both `services/api` and `libraries/utils/tasks/` without the tasks reaching up into api). Endpoint queries read the constant; list endpoints read the constant; any future deep-link handler reads the constant.
3. **One provider.** `ActivityBadgeProvider` is the single Riverpod source for both `notificationsCount` and `importsActionableCount`. The orphan `importsActionableBadgeProvider` is **DELETED** (not rewired). No parallel counts-provider lives on after this epic.
4. **Soft-archive before hard-delete for orphan rows.** Phase A of cleanup (this epic) sets `archived_at = NOW()` on orphan `import_*` user_activity rows — they become invisible to every UI and count query that already filters `archived_at IS NULL`, but remain in DB. Hard DELETE is a follow-up epic after one release of soak time. This buys us a rollback path if a missed downstream consumer surfaces.
5. **Import activity rows that exist only for push are dead weight.** Push dispatch reads `import_item` rows directly — that's the fact source. Parallel user_activity writes are a second source that drifts. New writes stop (abi-2a); orphan rows soft-archive (abi-2b).
6. **Backward compat for one release only.** Old `{count: int}` wrapper ships so pinned old clients don't break; new clients use the structured fields. Wrapper is marked deprecated in-line and removed in the release after `epic-activity-full-history` lands.
7. **Old-client fallback suppresses per-tab badges, not the bell.** When the new `{notifications, imports_actionable}` shape is missing (rolled-back deploy, server older than client), the Flutter client shows the bell's combined number (from `count`) but hides the per-tab badges — they'd otherwise attribute-misstate the split. Bell is always right; per-tab-badges are right or absent.
8. **Optimistic local decrement, server reconciliation ≤ 30s.** Archive/dismiss from the Imports tab decrements the bell number locally; the next 30s poll confirms or reverses. No server push to the bell.
9. **Bottom-nav tap destination is deterministic, not personalized.** Formula is `imports > notifications → imports else notifications`. Ties go to Notifications (cold-start default). No learning, no session memory, no hysteresis — the muscle-memory regression is accepted because Leo is the primary dogfooder and explicitly asked for tab-switch-to-actionable.
10. **Cold-start / loading-state fallback.** When counts haven't yet resolved on app launch, `initialTabFromCounts` returns `ActivityTab.notifications` (safe default). Once counts resolve, the tab switches **only if the user hasn't already manually swiped to a tab in this session** — no rug-pull on explicit user input.
11. **Queries run sequentially.** The two count queries in `unread_count` run on one DB session, back-to-back. No `asyncio.gather` — SQLAlchemy session-per-request + a shared pool make parallel gather false economy.
12. **Admin-only escape hatch.** `?include_system_types=true` on `list_activities` is behind the existing admin-role check. Non-admin users get a 403 if they pass the flag.
13. **Badge renders `99+` above 99.** Bottom-nav, Notifications-tab-badge, Imports-tab-badge all render `"99+"` when the count exceeds 99. Semantic label spells out the exact number for screen readers (`Semantics(label: "127 unread items")`), so accessibility isn't truncated even when the visual pill is.
14. **Unread `partner_action` rows older than 30d stay unread, invisible to the bell, reachable via See-all (Epic 2).** The 30d window scopes what bumps the bell; old unread rows remain in DB and surface in See-all after Epic 2 ships. No auto-mark-read sweep — an invisible-but-unread row is acceptable, and correcting it would require a background job the scope doesn't justify.

## File Structure (anticipated)

```
services/api/src/api/v1/user_activity/
├── unread_count.py                             # REWRITE — structured payload
├── list_activities.py                          # MODIFY — use NOTIFICATION_TAB_TYPES
└── tests/                                      # EXTEND

services/api/src/api/v1/import_job/
└── start_import.py                             # MODIFY — remove create_activity call

libraries/utils/utils/models/
└── user_activity.py                            # MODIFY — add NOTIFICATION_TAB_TYPES

libraries/utils/utils/tasks/import_tasks/
├── create_recipe_task.py                       # MODIFY — remove create_activity call
├── match_ingredients_task.py                   # MODIFY — remove create_activity call
├── extract_recipe_task.py                      # MODIFY — remove create_activity call
└── sweep_stuck_imports.py                      # MODIFY — remove create_activity call

services/migrator/migrations/versions/
└── XXXX_delete_orphan_import_user_activities.py  # NEW migration

app/lib/core/scaffolds/
└── scaffold_with_bottom_nav.dart               # MODIFY — read structured payload

app/lib/features/activity/providers/
├── activity_read_provider.dart                 # MODIFY — expose both count fields
├── imports_actionable_badge_provider.dart      # DELETE (or wire in) — resolve orphan
└── activity_tab_provider.dart                  # MODIFY — add initialTabFromCounts helper

app/lib/features/activity/
└── activity_screen.dart                        # MODIFY — use initialTabFromCounts on no-?tab entry
```

## Story Map (refined via party-mode 2026-04-20 — abi-2 split into abi-2a + abi-2b)

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| abi-1 | Backend: `unread-count` structured payload + `NOTIFICATION_TAB_TYPES` constant + `list_activities` type filter + admin-gated `?include_system_types` | 🔴 P0 | 1 d | None |
| abi-2a | Backend: delete orphan `import_*` `create_activity` call sites + push-dispatch regression test | 🔴 P0 | 0.5 d | abi-1 |
| abi-2b | Backend: soft-archive orphan `import_*` user_activity rows (migration sets `archived_at = NOW()`) with pre-migration row-count gate | 🔴 P0 | 0.25 d | abi-2a |
| abi-3 | Flutter: `ActivityBadgeProvider` reads structured payload + bottom-nav badge is the sum + 99+ rendering + old-client fallback suppresses per-tab badges | 🔴 P0 | 0.5 d | abi-1 |
| abi-4 | Flutter: bottom-nav tap → tab-with-more-items with cold-start safe default + delete orphan `importsActionableBadgeProvider` | 🟡 P1 | 0.5 d | abi-3 |
| abi-5 | Regression: end-to-end badge-integrity integration test (seed, tap, swipe, poll, 99+, cold-start, excluded-type, fake-timer poll) | 🟡 P1 | 0.5 d | abi-3, abi-4 |

**Total estimated effort: 3.25 days**

**Parallel tracks:**
- Backend track: abi-1 → abi-2a → abi-2b in series
- Frontend track: abi-3 → abi-4 in series after abi-1 payload contract lands
- abi-5 lands last as whole-stack proof

**Out-of-scope, tracked follow-up:** hard DELETE of the soft-archived orphan rows lives in a placeholder epic `epic-activity-orphan-cleanup` scheduled for one release after `epic-activity-full-history` ships.

---

## Story abi-1: Backend — `unread-count` structured payload + allow-list

As the Activity backend,
I want the unread-count endpoint to return separate counts for notifications and actionable imports, filtered by a single source-of-truth allow-list for notification types,
so that the frontend badge formula is a pure sum of two fields that exactly match what the two tab bodies render.

### Acceptance Criteria

1. `NOTIFICATION_TAB_TYPES` module-level constant in `libraries/utils/utils/models/user_activity.py`: a `frozenset[str]` or `tuple[str, ...]` exported at module top-level. Current membership: `('partner_action',)`. Adding a value here is the only way to make a `user_activity.type` visible in the Notifications tab or the bell.
2. `GET /v1/activities/unread-count` returns `{notifications: int, imports_actionable: int, count: int}`. `count = notifications + imports_actionable` (backward-compat wrapper, deprecated in docstring).
3. `notifications` query:
   ```sql
   SELECT COUNT(*) FROM user_activities
   WHERE user_id = ?
     AND read = false
     AND archived_at IS NULL
     AND type IN NOTIFICATION_TAB_TYPES
     AND created_at >= NOW() - INTERVAL '30 days';
   ```
   Plan confirmed via `EXPLAIN` in test to use the existing partial index `(user_id, created_at DESC) WHERE archived_at IS NULL`.
4. `imports_actionable` query:
   ```sql
   SELECT COUNT(*) FROM import_items
   WHERE user_id = ?
     AND archived_at IS NULL
     AND dismissed_at IS NULL
     AND status IN ('pending','processing','extracting','matching','awaiting_parser','awaiting_review','failed');
   ```
   Plan confirmed via `EXPLAIN` in test to use an index on `(user_id, status)`.
5. `GET /v1/activities` (`list_activities.py`) filters by `type IN NOTIFICATION_TAB_TYPES` by default. New optional query param `?include_system_types=true` restores the old behavior (returns import_* rows too) — used only for admin/debug.
6. Unit tests: seed 3 partner_action + 2 import_needs_review + 1 invitation (invitation type exists but isn't in the allow-list); call `GET /v1/activities/unread-count` → `{notifications: 3, imports_actionable: 2, count: 5}`. (The invitation is counted as `import_actionable`? No — invitation is a user_activity type, not an import status. Rewording: 3 partner_action + 2 import-items-awaiting-review + 1 invitation user_activity → `{notifications: 3, imports_actionable: 2, count: 5}`. The 1 invitation is excluded because `invitation` is not in the allow-list.)
7. Backward-compat test: pin a fixture that asserts the JSON body has the `count` field with the correct sum. One-release deprecation is marked with a module-level comment.
8. `include_archived=false` (default) on `list_activities` AND `type IN NOTIFICATION_TAB_TYPES` both apply simultaneously; an archived partner_action is excluded; an unarchived import_started is excluded.
9. `?include_system_types=true` on `list_activities` is admin-gated — a non-admin calling with the flag gets 403 `detail="admin_required"`. Admin gating reuses the existing admin-role middleware (same pattern as `/v1/admin/*`).
10. The two count queries in `unread_count` execute sequentially on one DB session (documented in the endpoint docstring) — no `asyncio.gather`, no session cloning.
11. Coverage stays at 100% on `services/api/src/api/v1/user_activity/`. The new allow-list constant has coverage via the import test in `libraries/utils/`.
12. Index plan verified: `EXPLAIN ANALYZE` in the test suite confirms the `notifications` count query uses the `(user_id, created_at DESC) WHERE archived_at IS NULL` partial index; the `imports_actionable` count query uses an `(user_id, status)` index. If no such index exists on `import_items`, the story adds a partial index `(user_id, status) WHERE archived_at IS NULL AND dismissed_at IS NULL`, concurrently-created per ahr-1 pattern.

### Key Files

- Modify: `libraries/utils/utils/models/user_activity.py` (add `NOTIFICATION_TAB_TYPES`)
- Modify: `services/api/src/api/v1/user_activity/unread_count.py` (new payload shape + dual query)
- Modify: `services/api/src/api/v1/user_activity/list_activities.py` (apply allow-list)
- Tests: `services/api/tests/api/v1/user_activity/test_unread_count.py`, `test_list_activities.py`

---

## Story abi-2a: Backend — delete orphan `import_*` activity writes at source

As the import pipeline,
I want to stop writing `import_*` rows to `user_activities` since the push-dispatch layer reads import_items directly,
so that the badge count and the Notifications tab never disagree with each other because of a parallel write path.

### Acceptance Criteria

1. The following `create_activity()` calls are deleted:
   - `services/api/src/api/v1/import_job/start_import.py:431` (`import_started`)
   - `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py:342` (`import_complete`)
   - `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py:149` (`import_needs_review`)
   - `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` (any `import_failed`)
   - `libraries/utils/utils/tasks/import_tasks/sweep_stuck_imports.py` (any `import_failed`)
2. For each deletion, a grep audit confirms no downstream reader. Push-dispatch code path reads from import_item, not user_activity — verified by reading `services/api/src/services/push_notifications.py` and related task code. The audit is documented in the story's implementation notes.
3. Push-dispatch regression: a needs-review import still triggers an FCM push. Proved by an integration test that seeds an import_item transitioning to `awaiting_review`, asserts the push-dispatch code path fires (mock FCM client).
4. Pipeline regression: run a synthetic import through start → parser → extractor → matcher. Assert no new `user_activities` row with `type LIKE 'import_%'` is created end-to-end. This is the load-bearing assertion of abi-2a — it makes abi-2b's soft-archive migration idempotent.
5. Existing `user_activity.type` tests that assert import_* types are CREATED are deleted. Replaced with tests that assert those types are NEVER created from the pipeline.
6. The allow-list (`NOTIFICATION_TAB_TYPES`, from abi-1) does not list any of the deleted types; re-inserts would not surface in the tab anyway — the goal here is to prevent the rows entirely.

### Key Files

- Modify: 5 files listed in AC1
- Modify or delete: relevant tests under `services/api/tests/` and `libraries/utils/` that assert import_* user_activity creation
- Verify: `services/api/src/services/push_notifications.py` (no changes expected, just confirmation)

---

## Story abi-2b: Backend — soft-archive orphan `import_*` user_activity rows

As the Activity backend,
I want existing orphan `import_*` user_activity rows to become invisible to the UI and count queries without being hard-deleted,
so that if a downstream consumer we missed surfaces after ship, we can reverse course by UPDATE rather than by restore-from-backup.

### Acceptance Criteria

1. New Alembic migration runs:
   ```sql
   UPDATE user_activities
      SET archived_at = NOW()
    WHERE type IN ('import_started','import_complete','import_needs_review','import_failed')
      AND archived_at IS NULL;
   ```
2. Pre-migration safety rail: the migration first runs `SELECT COUNT(*) FROM user_activities WHERE type IN (...) AND archived_at IS NULL` and logs it. **If count > 100_000, abort** with a clear log message ("aborting orphan soft-archive: N rows exceed 100k safety threshold; inspect manually") and exit non-zero. This forces a human decision on Leo's prod scale before large writes run.
3. A `service="audit"` error_logs row is written post-UPDATE with `error_type="SoftArchiveOrphanActivities"` and a payload of `{"affected_rows": N, "types": [...]}`. Idempotent with the audit log pattern already used by ops scripts.
4. Post-migration regression: `GET /v1/activities/unread-count` returns `{notifications: 0, imports_actionable: 0, count: 0}` in a test fixture that previously had N orphan rows. All rows filtered out because every list/count query already gates on `archived_at IS NULL`.
5. Rollback path is a single `UPDATE ... SET archived_at = NULL WHERE type IN (...) AND archived_at >= '<deploy_timestamp>'` — documented in the migration's upgrade/downgrade docstring.
6. Migration runs in one transaction (no `CONCURRENTLY` needed — UPDATE on indexed type column is fast). Uses `op.execute()` with a literal statement; does NOT use `CASCADE`.
7. Depends on abi-2a shipping first so the orphan creation pipeline is already closed when the soft-archive runs — otherwise new rows would leak past the migration.

### Key Files

- Create: `services/migrator/migrations/versions/XXXX_soft_archive_orphan_import_user_activities.py`
- Modify: tests asserting post-migration counts

---

## Story abi-2b-followup: Placeholder — hard DELETE orphan rows in a later release

Tracked in sprint-status as `epic-activity-orphan-cleanup` (not part of this epic's scope). After one release of soak time (post-`epic-activity-full-history`), if no downstream consumer has surfaced, a follow-up migration hard-DELETEs rows where `archived_at >= '<soft_archive_timestamp>'`. Kept as a forward-reference so it doesn't get lost.

---

## Story abi-3: Flutter — bottom-nav badge reads structured payload

As Leo,
I want the bell number in the bottom nav to match what's actually in the Activity tabs,
so that I can trust the number and not go hunting for phantom items.

### Acceptance Criteria

1. New `ActivityBadgeProvider` parses `GET /v1/activities/unread-count` response and exposes two fields: `notificationsCount` and `importsActionableCount`. The existing `ActivityReadProvider.unreadCount` is kept as a derived `notificationsCount + importsActionableCount` for any downstream reader that still uses it.
2. `scaffold_with_bottom_nav.dart:64-66` reads the sum. Badge renders `notificationsCount + importsActionableCount`. No separate glyph, no separate color based on source.
3. **99+ rendering.** When the combined sum exceeds 99, the badge pill renders `"99+"`. Same rule for the Notifications-tab badge and the Imports-tab badge (in-tab). Under-99 values render as-is.
4. **Semantic label spells out the exact count** for screen readers via `Semantics(label: "N unread items")` — accessibility is not truncated at 99+.
5. **Old-client fallback.** When the server returns only `{count: int}` (no `notifications`/`imports_actionable` keys — rolled-back deploy), the bottom-nav badge still renders `count`; per-tab badges hide entirely rather than mis-attribute the split. A structured-log warning fires once per session: `"badge: old payload shape detected, per-tab badges suppressed"`.
6. Polling cadence unchanged (30s). Riverpod provider debounces count updates with 100ms to prevent flicker. This debounce is load-bearing AC (lifted from NFR-ABI-3): the badge must not visibly flash on 30s refresh when the count is unchanged.
7. Regression: existing activity-badge widget tests in `app/test/features/activity/` pass unmodified or are updated to assert against the new payload shape.
8. Widget test: pump `ScaffoldWithBottomNav` with a stub provider returning `{notifications: 2, imports_actionable: 3}`. Assert badge text reads `"5"`. Switch to `{notifications: 0, imports_actionable: 0}`. Assert no badge rendered.
9. 99+ test: stub `{notifications: 50, imports_actionable: 80}`; assert badge text reads `"99+"`; assert `Semantics` label reads `"130 unread items"`.
10. Old-client fallback test: stub a response with only `{count: 7}`; assert bottom-nav shows `"7"`; assert Notifications and Imports in-tab badges are absent (no zero-badge, no wrong-attribution).

### Key Files

- Modify: `app/lib/core/scaffolds/scaffold_with_bottom_nav.dart`
- Modify: `app/lib/features/activity/providers/activity_read_provider.dart`
- Tests: `app/test/features/activity/providers/activity_read_provider_test.dart`, `app/test/core/scaffolds/scaffold_with_bottom_nav_test.dart`

---

## Story abi-4: Flutter — bottom-nav tap destination + orphan provider resolution

As Leo,
I want tapping the Activity tab to land me on whichever side has more to act on,
so that I'm not chasing down a number by switching tabs after I tap.

### Acceptance Criteria

1. New helper `initialTabFromCounts(int notifications, int importsActionable) → ActivityTab`: returns `ActivityTab.imports` if `importsActionable > notifications`, else `ActivityTab.notifications`. Lives next to `activity_tab_provider.dart`.
2. `ActivityScreen` on `initState` (or Riverpod build) checks for an explicit `?tab=` query param in the current route. If present, use it (current behavior). If absent, call `initialTabFromCounts` with the latest-known counts.
3. **Cold-start loading-state behavior.** When the badge provider hasn't yet resolved (first-ever app launch, cache cleared, logout → login), `initialTabFromCounts` is called with `(0, 0)` → returns Notifications (safe default). Once counts resolve asynchronously, the tab auto-switches **only if the user has NOT already swiped manually in this session** — a `bool _userTouchedTab` flag on `ActivityScreen` latches true on any tap/swipe and blocks the auto-switch. No rug-pull.
4. **Orphan provider deletion.** `app/lib/features/activity/providers/imports_actionable_badge_provider.dart` is **deleted**. Every call site that used it now reads `ActivityBadgeProvider.importsActionableCount`. The resolution is explicit — not "(a) rewired or (b) deleted" — it's DELETE. No dead code after this story.
5. Imports tab badge (inside `ActivityScreen`'s tab strip) continues to read its per-tab count from `ActivityBadgeProvider.importsActionableCount`. Same for Notifications from `.notificationsCount`.
6. Push-payload deep-link regression: a push with explicit `?tab=imports` still opens Imports tab even if Notifications has more items.
7. Widget test: pump `ActivityScreen` with stub counts `{notifications: 1, imports: 3}`, no `?tab=`; assert `TabController.index` == Imports. Swap to `{notifications: 3, imports: 1}`; assert `.index` == Notifications. Swap to `{notifications: 2, imports: 2}`; assert `.index` == Notifications (tie breaker).
8. Deep-link test: open `/activity?tab=notifications` with counts `{notifications: 0, imports: 5}`; assert Notifications tab opens (explicit param wins).
9. Cold-start test: pump `ActivityScreen` with `AsyncLoading` counts, no `?tab=`; assert Notifications opens. Resolve with `{notifications: 1, imports: 5}`; assert `.index` auto-switches to Imports. Repeat but tap Notifications manually first (before counts resolve); resolve with `{notifications: 1, imports: 5}`; assert `.index` stays Notifications (manual override latched).

### Key Files

- Modify: `app/lib/features/activity/providers/activity_tab_provider.dart`
- Modify: `app/lib/features/activity/activity_screen.dart`
- Delete or rewire: `app/lib/features/activity/providers/imports_actionable_badge_provider.dart`
- Tests: `app/test/features/activity/activity_screen_test.dart`, `app/test/features/activity/providers/activity_tab_provider_test.dart`

---

## Story abi-5: End-to-end badge integrity regression

As Leo,
I want the badge to stay accurate through a full cycle (new activity arrives, I tap and read, I archive, I dismiss),
so that I never catch the app lying to me about what's waiting.

### Acceptance Criteria

1. Integration test: seed 2 partner_action user_activities (unread) + 1 failed import_item + 2 needs-review import_items + 1 completed green import_item. Cold-start bottom-nav: badge reads `5` (2 notifications + 3 imports_actionable; green excluded).
2. Same test continues: tap the Activity tab. Assert Imports tab opens first (3 > 2). Imports tab in-tab badge reads `3`; Notifications tab in-tab badge reads `2`.
3. Swipe-archive one failed import. Assert: optimistic local bottom-nav drop to `4`. Fast-forward a fake timer by 30s to simulate the poll; assert `4` confirmed. Imports tab in-tab badge == `2`; Notifications tab in-tab badge == `2`.
4. Switch to Notifications tab. Mark-all-read fires; notifications count drops to `0`. Assert: bottom-nav reads `2` (imports only). Notifications in-tab badge == `0`.
5. Simulate a new partner_action push arriving while app is foregrounded. Fast-forward the fake timer 30s; assert next poll bumps notifications to `1`; bottom-nav reads `3`; in-tab badges sum to `3`.
6. **Sum invariant assertion: at every step above, `bottom_nav_badge == notifications_tab_in_badge + imports_tab_in_badge`.** Load-bearing invariant of the epic.
7. Type-allow-list regression: run a synthetic pipeline through start_import → parser → extractor → matcher. Assert `SELECT COUNT(*) FROM user_activities WHERE type LIKE 'import_%'` is `0` throughout. (Verifies abi-2a stays clean.)
8. Excluded-type regression: seed an `invitation` user_activity (type not in `NOTIFICATION_TAB_TYPES`). Assert bottom-nav does NOT increment. Assert the row is absent from both the Notifications list and the bell count.
9. Push-dispatch regression: assert needs-review push still arrives (mocked FCM receiver) even though no user_activity row is written. Proves the push path reads import_item directly.
10. 99+ regression: seed 150 actionable imports + 0 notifications; assert bottom-nav renders `"99+"`; assert Imports tab in-badge renders `"99+"`; assert `Semantics` label reads `"150 unread items"`.
11. Cold-start regression: cold-start with empty Riverpod cache and seeded server-side counts `{notifications: 0, imports: 5}`; assert the tab initially renders Notifications (safe default) and switches to Imports only after counts resolve AND the user hasn't touched a tab.
12. Single-device scope note: this integration test is scoped to single-device behavior. Multi-device read-state sync is explicitly a non-goal (per PRD addendum "No cross-device push inbox"). A comment at the top of the test file documents this scope boundary.
13. Uses a fake-clock / `FakeAsync` test harness so the 30s poll window is fast-forwarded; does not literally wait 30 seconds per assertion.

### Key Files

- Tests: `app/integration_test/features/activity/badge_integrity_test.dart` (new file) — full widget + mock server + seeded data
- Backend integration harness: `services/api/tests/integration/test_badge_integrity_flow.py`

---

## Dependencies

- **Cross-epic:** `epic-activity-full-history` depends on `NOTIFICATION_TAB_TYPES` and the new `unread-count` payload shape landed by this epic.
- **Backwards compat:** one release of old `{count: int}` wrapper for pinned clients; removed in the release after `epic-activity-full-history`.
- **No merge-freeze collision** with other in-flight work on the Activity Hub (none currently).

## Open Questions for the User

None blocking — all three locked decisions (combined bell, unbounded pagination, See-all footer pattern) answer the Phase 2 questions. Party-mode (Phase 6) may surface edge cases (e.g. guest-session behavior, multi-device read-state) that get escalated before abi-3 begins.

## Definition of Done (Epic Level)

- `GET /v1/activities/unread-count` returns the structured payload with `notifications`, `imports_actionable`, and backward-compat `count`.
- `NOTIFICATION_TAB_TYPES` constant is the single source of truth; `list_activities` and `unread_count` both read from it.
- No `import_*` user_activity rows written by the pipeline; orphan migration has cleared existing rows.
- Bottom-nav badge = sum of notifications + imports_actionable. Green excluded.
- Tap on Activity tab without explicit `?tab=` lands on the tab with more items (tie → Notifications).
- No drift: the sum-invariant test passes across a full cycle of new-activity / read / archive / dismiss.
- Push-dispatch for needs-review imports still works end-to-end.
- 100% coverage on `services/api`; new Flutter widget tests cover the badge formula and tap destination.
