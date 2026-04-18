<!-- refined via party-mode 2026-04-18 -->
# Epic: Activity Hub Redesign — Two-Tab Shell + Color-Coded Imports

## Overview

The Activity Hub has been iterated on three times (Epic 13 unified-import-pipeline, Epic MVP Finalization swipe/retry/dismiss, epic-bugs-activity-hub polish) and still feels muddled to Leo because imports and general notifications share one feed with a filter-chip redirect. The `/activity?filter=imports` chip silently jumps to a separate `/activity/import-history` screen — users learn this by accident. The two concerns are conceptually separate and the IA should make that obvious.

This epic rebuilds the Activity Hub as a **single route with two tabs**: **Notifications** (invitations / partner_action / meal_reminder) and **Imports** (all import-sourced activity, sectioned by state with fixed color semantics). Blue = In Progress, Yellow = Needs Review, Red = Failed, Green = Auto-Imported. Swipe-to-archive works everywhere except blue (cancel-in-progress stays a detail-screen flow). A "See all" footer holds archived imports + >30d history in muted type.

This epic does NOT rebuild the per-row detail view itself — it ships the shell, sections, and swipe rules. Rich per-row caret expansion + telemetry + confidence rendering lands in `epic-import-row-rich-detail` next.

## Goal

Leo opens `/activity` and instantly sees two clean siblings — general notifications on one tab, imports on the other, with the import states visually segregated by color and sorted most-recent-first. Swipe-to-archive is predictable (every row except In Progress). "See all" is the escape hatch for old stuff. No filter-chip redirects, no two-route confusion.

## End-User Flow

1. Leo taps the **Activity** tab in the bottom nav.
2. Lands on `/activity` — sees two tabs at the top: **Notifications** (selected by default on cold start) and **Imports**. The tab strip is sticky under the app bar.
3. Notifications tab shows a chronological list of invitations, partner activity, and meal reminders. Swipes one left → row archives with a 3s snackbar-undo.
4. Taps **Imports** → sees four header chips stacked top-to-bottom: **In Progress** (blue, 2), **Needs Review** (yellow, 3), **Failed** (red, 1), **Auto-Imported** (green, 4). Under each chip, rows for imports in that state, most-recent-first. Empty sections are hidden entirely.
5. Swipes a green (Auto-Imported) row left → 3s snackbar-undo → row archives and disappears from the green section.
6. Tries to swipe a blue (In Progress) row → nothing happens (no swipe affordance rendered for blue).
7. Scrolls to the bottom of the Imports tab, taps **See all (7)** → the footer expands to reveal archived imports + items older than 30 days in muted typography. Taps **See all** again → collapses.
8. Closes the app, reopens, returns to `/activity` — Notifications tab is selected again (cold-start default, session-remembered tab is discarded).
9. Opens a push notification for a needs-review import → deep-links to `/activity?tab=imports` → Imports tab is preselected; Leo taps the specific yellow row → opens the existing item-detail review flow.
10. On Add Recipe, the slim `LiveImportStrip` still reads "2 imports in progress ›" and deep-links to `/activity?tab=imports` — unchanged behavior, one-liner.

## Frontend Changes

**Required — heavy.** This is the bulk of the epic.

- **New tab widget** at the top of `ActivityScreen`. Two tabs, `TabBar` + `TabBarView`. Tab selection state held in a `StateProvider<ActivityTab>`; initial value `ActivityTab.notifications` on cold start; subsequent tab switches within the session remembered via the same provider (discarded on app restart).
- **Notifications tab body.** Reuses the existing chronological activity-row rendering (`_ActivityRow` pattern from today's `activity_screen.dart`) but filtered to non-import activity types only (`invitation`, `partner_action`, `meal_reminder`). Retains today's tab-open mark-all-read behavior (bugs-act-1). New: swipe-to-archive per row calling the new `POST /v1/user-activities/{id}/archive` endpoint; archived rows disappear from the feed.
- **Imports tab body.** New layout: four `ImportStateSection` widgets stacked — In Progress, Needs Review, Failed, Auto-Imported — each with a header chip (section name + count) and a list of `ImportRow` widgets for items in that state, sorted by `created_at DESC`. Empty sections render nothing (no placeholder). A fifth collapsed `SeeAllSection` at the bottom wraps archived + >30d items.
- **`ImportRow` widget (shell only).** Source-type icon + recipe name + 1-line status label + colored state chip + relative timestamp + trailing chevron. This epic ships the collapsed row layout; the caret-expansion is the next epic's scope, but the row leaves a `trailing` slot reserved for the caret toggle and lays out chrome that can accommodate both collapsed + expanded heights without flicker.
- **Semantic color tokens.** Add to `app/lib/theme/` a new `ImportStateColors` extension on `ThemeData` with fields `inProgress`, `needsReview`, `failed`, `autoImported` — maps to Material3 `colorScheme.primary` / `tertiary` / `error` / `secondary` today, but **every reference in import-related code goes through the token from now on**, so future color tuning happens in one place.
- **Swipe wiring.** Notifications rows: swipe archives via new `POST /v1/user-activities/{id}/archive`. Needs-Review / Failed / Auto-Imported import rows: swipe archives via `POST /v1/import-items/{id}/archive` (new — this epic adds it alongside the activity-archive endpoint; distinct from the existing `dismiss` which is a different concept — dismiss means "I've decided not to import this"; archive means "hide from the main feed"). Blue (In Progress) rows render no `Dismissible` wrapper at all — the swipe affordance is absent, not just ignored.
- **Undo snackbar.** 3s duration, restores the row in-place on tap. Archive endpoints are idempotent so a second restore after the snackbar dismisses is a no-op.
- **"See all" footer.** Collapsed by default showing just a `See all (N) ›` row; expanded reveals archived + >30d items rendered with muted typography (opacity 0.65). The section sorts by archive timestamp when available, else `created_at DESC`.
- **Routing.** `/activity` stays the single route. Query param `tab=<notifications|imports>` selects the tab. `/activity?filter=imports` continues to work for one release, mapped forward to `?tab=imports`. The separate route `/activity/import-history` is removed from the router; any deep-link to it rewrites to `/activity?tab=imports` at router level. Removal of the `ImportHistoryScreen` widget file is deferred to the release after this epic ships (per PRD out-of-scope).
- **`LiveImportStrip` on `AddRecipeSheet`.** No functional change. The existing deep-link updates to `/activity?tab=imports`.
- **Empty states.** Imports tab with zero imports of any state renders a single centered "All clear — no imports yet" card. Notifications tab with zero items renders "You're all caught up".

## Backend Changes

**Required — small.** Archive is a new concept on the user-activity model + ImportItem model.

- **`user_activities` schema.** Add `archived_at TIMESTAMPTZ NULL` column via a new migration. Existing `updated_at` is sufficient for list-ordering; `archived_at` is nullable and semantically orthogonal. `archived_at IS NOT NULL` excludes the row from default feed queries.
- **`import_items` schema.** Add `archived_at TIMESTAMPTZ NULL` column. Distinct from `dismissed_at` (which already exists — dismiss means "I looked at this failed/review item and decided not to import it"). Archive means "hide this from the main Imports tab, but keep it in See-all history".
- **`POST /v1/user-activities/{id}/archive`.** Sets `archived_at = NOW()`. Idempotent (second call is a no-op). Ownership check (user must own the activity). Returns the updated activity.
- **`POST /v1/import-items/{id}/archive`.** Sets `archived_at = NOW()`. Same idempotency + ownership. Cannot archive an item whose status is `pending`, `extracting`, `matching`, or `processing` — returns 409 with `detail="cannot archive in-progress import"`. This enforces the "blue is read-only" rule at the API layer, not just the UI.
- **Undo path.** Clients call the same endpoint's sibling `POST /v1/user-activities/{id}/unarchive` and `POST /v1/import-items/{id}/unarchive` to reverse. Both set `archived_at = NULL`. Idempotent.
- **List endpoints.** `GET /v1/user-activities` and `GET /v1/import-jobs` (and `GET /v1/import-items`) gain a `?include_archived=<bool>` query parameter defaulting to `false`. Clients fetching the Notifications tab or the four Imports sections pass `false`; clients fetching the See-all footer pass `true`. Additionally `GET /v1/import-jobs?archived_only=true` returns archived + >30d items for the See-all section.
- **No new activity types**, no changes to `user_activity.type` values, no changes to existing notification push logic.

## Infrastructure Changes

**None.**

- No new AWS resources. The two new columns + endpoints run on existing RDS + FastAPI infra. The migration is standard Alembic via `services/migrator/`.
- No env var changes, no IAM changes, no Terraform changes.

## Design Principles (refined via party-mode 2026-04-18)

1. **Two tabs, one route.** `/activity` is the single entry point. Tabs are top-of-screen, not bottom-nav. Tab state is session-remembered but cold-start defaults to Notifications.
2. **Color semantics are locked.** BLUE / YELLOW / RED / GREEN mean In Progress / Needs Review / Failed / Auto-Imported everywhere. Codified as `ImportStateColors` theme extension (token names: `inProgress`, `needsReview`, `failed`, `autoImported`). No bare `colorScheme.X` references for import state after this epic.
3. **Blue is read-only — and looks it.** No swipe on In Progress. API enforces with `SELECT ... FOR UPDATE` + status recheck. Visually, blue rows replace the trailing chevron with a non-interactive progress glyph so the read-only-ness is self-evident.
4. **Archive ≠ dismiss — they're orthogonal filters.** Dismiss is "I decided not to import"; archive is "hide from main feed, keep findable in See-all". Distinct backend fields (`dismissed_at` vs `archived_at`). Default list query is `archived_at IS NULL AND dismissed_at IS NULL`. See-all list is `archived_at IS NOT NULL OR (status=completed AND created_at < now-30d)`.
5. **Partial indexes on the default hot path.** For any new "hide from feed" flag column, use partial indexes (`WHERE archived_at IS NULL`) rather than composite indexes on a nullable flag. Migrations run these `CONCURRENTLY` — Alembic block exits the transaction before the concurrent index creation.
6. **Optimistic archive survives an intervening poll.** A row locally archived stays archived even if the next 30s poll returns it with a new server status — until the archive endpoint's HTTP response settles one way or the other.
7. **Tap destinations per color state are fixed.** Blue → in-progress detail; Yellow/Red → review detail; Green → the created recipe. Rich-detail epic's caret expansion is additive on top of tap; tap behavior doesn't change.
8. **See-all footer stays muted via a theme-aware token.** `colorScheme.onSurface.withOpacity(0.65)`, never raw `Opacity(0.65)`, so dark mode stays legible.
9. **`LiveImportStrip` stays.** It's a link, not a duplicate. Rich view is in the Imports tab.
10. **No new bottom-nav tab.** Single Activity tab in bottom nav.

## File Structure (anticipated)

```
app/lib/features/activity/
├── activity_screen.dart                      # MAJOR REWRITE — two-tab shell
├── notifications_tab.dart                    # NEW — non-import activity feed
├── imports_tab.dart                          # NEW — four color sections + See-all
├── widgets/
│   ├── import_state_section.dart             # NEW — section header chip + list
│   ├── import_row.dart                       # NEW — collapsed row layout (shell only)
│   ├── see_all_footer.dart                   # NEW — collapsible archived + >30d list
│   ├── activity_filter_chips.dart            # DELETE — tabs replace chips
│   └── import_activity_detail.dart           # KEPT — reused later by caret expansion
└── providers/
    ├── activity_tab_provider.dart            # NEW — session-scoped selected tab
    ├── activity_archive_provider.dart        # NEW — optimistic archive state
    └── activity_read_provider.dart           # KEPT — read-state caching (bugs-act-1)

app/lib/theme/
└── import_state_colors.dart                  # NEW — semantic color tokens extension

app/lib/features/recipes/add_recipe/widgets/
└── live_import_strip.dart                    # MODIFIED — deep-link to ?tab=imports

app/lib/core/router/app_router.dart           # MODIFIED — remove /activity/import-history route; rewrite legacy filter query

services/api/src/api/v1/user_activity/
├── archive_activity.py                       # NEW — POST /v1/user-activities/{id}/archive
├── unarchive_activity.py                     # NEW — POST /v1/user-activities/{id}/unarchive
└── list_activities.py                        # MODIFIED — support ?include_archived

services/api/src/api/v1/import_job/
├── archive_import_item.py                    # NEW — POST /v1/import-items/{id}/archive
├── unarchive_import_item.py                  # NEW — POST /v1/import-items/{id}/unarchive
├── list_import_jobs.py                       # MODIFIED — ?include_archived, ?archived_only
└── list_import_items.py                      # MODIFIED — ?include_archived

libraries/utils/utils/models/
├── user_activity.py                          # MODIFIED — add archived_at column
└── import_item.py                            # MODIFIED — add archived_at column

services/migrator/migrations/versions/
└── XXXX_add_archived_at_to_activities_and_import_items.py  # NEW migration
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| ahr-1 | Backend: `archived_at` columns, archive/unarchive endpoints, `?include_archived` query param | 🔴 P0 | 1 d | None |
| ahr-2 | Flutter: `ActivityScreen` two-tab shell + tab provider + routing rewrite | 🔴 P0 | 1 d | ahr-1 (for endpoint contracts) |
| ahr-3 | Flutter: Notifications tab — chronological feed + swipe-to-archive + undo | 🟡 P1 | 0.5 d | ahr-2 |
| ahr-4 | Flutter: Imports tab — four color sections + `ImportRow` shell + swipe rules (blue read-only) | 🔴 P0 | 1.5 d | ahr-2, ahr-1 |
| ahr-5 | Flutter: See-all footer + archived/older-than-30d rendering + muted typography | 🟡 P1 | 0.5 d | ahr-4 |
| ahr-6 | Flutter: `ImportStateColors` theme extension + full audit of color refs in import code | 🟡 P1 | 0.5 d | ahr-4 |
| ahr-7 | Retire `/activity/import-history` route + `LiveImportStrip` deep-link update + regression audit | 🟡 P1 | 0.5 d | ahr-4, ahr-5 |

**Total estimated effort: 5.5 days**

**Parallel tracks:**
- Track A (backend): ahr-1 ships first — unblocks all frontend work
- Track B (frontend shell): ahr-2 → ahr-3 (Notifications) + ahr-4 (Imports) can then fan out
- Track C (polish): ahr-5, ahr-6, ahr-7 follow ahr-4

---

## Story ahr-1: Backend — archive columns + endpoints + list filters

As the Activity Hub backend,
I want to distinguish archived activities and import items from active ones, and to reject archive calls on in-progress imports,
so that the frontend can implement "swipe-to-archive except for blue" without client-side hacks.

### Acceptance Criteria

1. New Alembic migration adds `archived_at TIMESTAMPTZ NULL` to both `user_activities` and `import_items`. Creates **two partial indexes per table**: the hot-path index `(user_id, created_at DESC) WHERE archived_at IS NULL` (for default feed queries) and the See-all index `(user_id, archived_at DESC) WHERE archived_at IS NOT NULL`.
2. Partial indexes are created with `postgresql_concurrently=True`; the Alembic migration exits its transaction (`op.execute("COMMIT")`) before issuing `CREATE INDEX CONCURRENTLY`, then reopens a transaction for any follow-up DDL. Prevents deploy-time table locks on RDS.
3. `POST /v1/user-activities/{id}/archive` sets `archived_at = NOW()` if NULL, else no-op. Returns 200 with the updated row. 403 if not owner.
4. `POST /v1/user-activities/{id}/unarchive` sets `archived_at = NULL`. Idempotent.
5. `POST /v1/import-items/{id}/archive` uses `SELECT ... FOR UPDATE` inside the transaction, re-reads `status` under lock, and returns 409 `detail="cannot archive in-progress import"` if `status IN ('pending','extracting','matching','processing')`. Otherwise sets `archived_at = NOW()`. 403 if not owner. This closes the webhook race where a row flips to in-progress between the initial read and the write.
6. Archive operates independently of dismiss (`dismissed_at`); both are orthogonal filters. A dismissed-then-archived item is returned only when a caller passes both `include_dismissed=true` AND `include_archived=true` (or `archived_only=true`). Default list queries exclude both.
7. `POST /v1/import-items/{id}/unarchive` sets `archived_at = NULL`. Idempotent.
8. `GET /v1/user-activities` and `GET /v1/import-jobs`, `GET /v1/import-items` accept `?include_archived=<bool>` (default false). When false, queries filter `archived_at IS NULL AND dismissed_at IS NULL`. When true, returns both sets.
9. `GET /v1/import-jobs` and `GET /v1/import-items` also accept `?archived_only=<bool>` (default false) that returns only rows with `archived_at IS NOT NULL`. `archived_only=true` implies `include_archived=true`; passing `archived_only=true&include_archived=false` returns 400 with `detail="contradictory filters"`.
10. Idempotency is proven by tests: calling archive twice is a 200 both times; body matches. Calling unarchive on an already-active row is a 200 no-op.
11. 409 path is proven by tests: seed an in-progress ImportItem, call archive, assert 409. Race test (optional but recommended): two concurrent archive calls on the same awaiting-review item — one succeeds, the other is a 200 no-op (not a 409 — idempotency wins).
12. Archive/unarchive mutations are NOT audit-logged (per locked-decision scope — audit is for admin mutations).
13. Integration test: create an activity, archive it, list with `include_archived=false` → not present; list with `include_archived=true` → present with `archived_at` set.
14. Query-plan assertion: `EXPLAIN ANALYZE` the default list query in the test suite and assert it uses the partial index (not a seq scan).

### Key Files

- Create: `services/migrator/migrations/versions/XXXX_add_archived_at_to_activities_and_import_items.py`
- Modify: `libraries/utils/utils/models/user_activity.py`, `libraries/utils/utils/models/import_item.py`
- Create: `services/api/src/api/v1/user_activity/archive_activity.py`, `unarchive_activity.py`
- Create: `services/api/src/api/v1/import_job/archive_import_item.py`, `unarchive_import_item.py`
- Modify: `services/api/src/api/v1/user_activity/list_activities.py`
- Modify: `services/api/src/api/v1/import_job/list_import_jobs.py`, `list_import_items.py`
- Wire new endpoints into routers.
- Tests: `services/api/tests/api/v1/user_activity/`, `services/api/tests/api/v1/import_job/`

---

## Story ahr-2: Flutter — `ActivityScreen` two-tab shell + routing

As Leo,
I want the Activity screen to show two clear tabs (Notifications | Imports) instead of a filter chip that secretly redirects to another screen,
so that I can tell at a glance where each concern lives.

### Acceptance Criteria

1. `ActivityScreen` renders a `TabBar` at the top with two tabs: "Notifications" and "Imports". `TabBarView` holds the two tab bodies.
2. New `StateProvider<ActivityTab>` (`activityTabProvider`) is the **source of truth** for tab selection; it is app-scoped (not `autoDispose`). On app cold-start it initializes to `ActivityTab.notifications` via an `AppLifecycleListener` that resets the provider. `TabController` listens to the provider (debounced 100ms on controller-driven changes to avoid feedback loop) and both directions stay in sync.
3. Query param `?tab=<notifications|imports>` on `/activity` preselects the tab on open. Legacy `?filter=<all|imports|partner|reminders>` is accepted for one release and mapped forward: `imports` → `tab=imports`, `all|partner|reminders` → `tab=notifications`. **When both `tab` and `filter` are present, `tab` wins.**
4. The old `/activity/import-history` route is removed from `app_router.dart`. A router-level redirect rewrites any navigation to that path → `/activity?tab=imports`. The redirect fires for both in-app navigations AND initial-route handling (cold-start from a push payload).
5. Tab selection visual: Material3 `TabBar` with indicator matching the theme's `primary` color. Both tabs render their badge count. Notifications tab badge = unread non-import activities. **Imports tab badge = actionable imports only (in-progress + needs-review + failed); green is excluded.** The bottom-nav Activity tab's imports contribution uses the same formula so the numbers never disagree.
6. Cold-start default tab regression test: seed one unread invitation + one in-progress import; cold-start; assert Notifications tab is active on load.
7. Deep-link test: open `/activity?tab=imports`; assert Imports tab is selected.
8. Legacy query test: open `/activity?filter=imports`; assert router maps to `?tab=imports` and Imports tab is selected.
9. Tie-breaker test: open `/activity?tab=notifications&filter=imports`; assert Notifications tab is selected (tab wins).
10. Cold-start push-payload test: simulate app launch with an initial URL of `/activity/import-history` (legacy push payload); assert the app lands on `/activity?tab=imports`.

### Key Files

- Major rewrite: `app/lib/features/activity/activity_screen.dart`
- Create: `app/lib/features/activity/providers/activity_tab_provider.dart`
- Modify: `app/lib/core/router/app_router.dart`
- Delete (widget delete deferred; route delete only): route `/activity/import-history` from router
- Tests: `app/test/features/activity/activity_screen_test.dart`

---

## Story ahr-3: Flutter — Notifications tab (feed + swipe-to-archive)

As Leo,
I want to swipe left on any notification to archive it with a quick undo,
so that I can clear my feed without accidentally losing something.

### Acceptance Criteria

1. `NotificationsTab` widget renders a chronological list of non-import `user_activity` rows (types: `invitation`, `partner_action`, `meal_reminder`), sorted `created_at DESC`.
2. Each row is wrapped in a `Dismissible` with swipe-left behavior. Swipe completes → row is optimistically removed; `POST /v1/user-activities/{id}/archive` is fired.
3. A 3s snackbar appears with "Archived · Undo". Tapping Undo restores the row and fires `POST /v1/user-activities/{id}/unarchive`.
4. If the archive API fails, the row re-appears and an error snackbar shows "Couldn't archive, try again". Optimistic removal is reversed.
5. Tab-open mark-all-read behavior from bugs-act-1 is preserved: opening the Notifications tab marks all loaded items read.
6. List uses `Dismissible` wrapped in `SizeTransition` for the removal animation. (Deliberate choice over `AnimatedList` — mixing `AnimatedList` with `Dismissible` is fragile because both want to own insert/remove animations.)
7. Empty state: "You're all caught up" centered card.
8. Polling: on-tab-visible polls every 30s; paused when tab is not visible.
9. Integration test: seed 2 activities, swipe the first, assert it's gone from list + API call fired; tap Undo, assert it's back.
10. Error-path test: seed 1 activity, stub API to fail, swipe, assert row is restored and error snackbar shows.

### Key Files

- Create: `app/lib/features/activity/notifications_tab.dart`
- Create: `app/lib/features/activity/providers/activity_archive_provider.dart`
- Modify: (reuse) `app/lib/features/activity/providers/activity_read_provider.dart`
- Tests: `app/test/features/activity/notifications_tab_test.dart`

---

## Story ahr-4: Flutter — Imports tab (four color sections + swipe rules)

As Leo,
I want the Imports tab to show my imports grouped by state (blue / yellow / red / green) with the ones I need to deal with on top, and with a swipe to archive on every row except the in-progress ones,
so that I always know what to do first and can clean up clutter without accidentally cancelling a running import.

### Acceptance Criteria

1. `ImportsTab` widget renders four stacked sections, top-to-bottom: **In Progress**, **Needs Review**, **Failed**, **Auto-Imported**.
2. Each section has a `SectionHeaderChip` showing the section name + count (e.g., "Needs Review · 3"). Section header uses its state's color token from `ImportStateColors`.
3. Rows inside a section are `ImportRow` widgets sorted `created_at DESC` for In Progress / Needs Review / Failed; `completed_at DESC` for Auto-Imported.
4. Empty sections are hidden entirely (not rendered with "0 items" placeholder).
5. **All-sections-empty state:** when every section is empty (regardless of See-all), the tab body renders an "All clear — no imports yet" centered card. **First-run variant:** when the user has zero lifetime imports (server returns `total_lifetime_imports: 0` on the list endpoint), render a dedicated first-run illustration + onboarding copy ("Paste a URL, snap a photo, or try the share sheet to import your first recipe").
6. `ImportRow` collapsed layout: source-type icon + recipe name (`Expanded` with ellipsis) + 1-line status label + colored state chip + relative timestamp + trailing slot. **`ImportRow` exposes a named `trailing` parameter** (`Widget? trailing`) so the rich-detail epic can slot in a caret toggle without a signature rewrite. Tap target is ≥48dp (Material guideline).
7. **Trailing slot default per state:**
   - Blue (In Progress): trailing is a non-interactive progress glyph (small `CircularProgressIndicator` at the chevron position) — visually self-evident read-only.
   - Yellow / Red / Green: trailing is a chevron (gets replaced by a caret toggle in the rich-detail epic).
8. **Tap destinations (fixed per state):**
   - Blue → existing in-progress detail route.
   - Yellow / Red → existing `/recipes/import/review/:itemId` review screen.
   - Green → the created recipe's detail route (`created_recipe_id`).
   These destinations are locked; the rich-detail epic's caret expansion is **additive** to tap, not a replacement.
9. **Swipe rules:** Needs Review / Failed / Auto-Imported rows are wrapped in `Dismissible` + `SizeTransition` removal animation with swipe-left archive + 3s undo snackbar. **In Progress rows render NO `Dismissible` wrapper** — no swipe affordance at all.
10. **Optimistic archive survives intervening polls:** a row locally marked archived stays hidden even if the next 30s poll returns it with a new server status, until the archive endpoint's HTTP response settles. If the response is a 409 (item flipped to in-progress mid-swipe), restore the row with an error snackbar "Can't archive while importing".
11. Polling: on-tab-visible polls every 30s for each state via the existing status-scoped list endpoints; paused when tab is not visible.
12. Imports tab badge reflects **actionable imports only** (in-progress + needs-review + failed). Green is excluded. Same formula as ahr-2 AC5.
13. State-to-section mapping is explicit:
    - In Progress: `status IN (pending, processing, extracting, matching, awaiting_parser)` or batches with `status IN (pending, submitted, running)`
    - Needs Review: `status = awaiting_review`
    - Failed: `status = failed`
    - Auto-Imported: `status = completed` AND `created_recipe_id IS NOT NULL`
14. Integration test: seed one item per section, assert each renders in its section with the right color chip.
15. Blue-read-only test: seed an in-progress item, run `await tester.drag(find.byType(ImportRow).first, const Offset(-500, 0))`, then `expect(find.byType(DismissibleBackground), findsNothing)` AND no archive API call fires.
16. Tap-destination tests (per state): seed one row per state, tap each, assert navigation to the locked destination route.

### Key Files

- Create: `app/lib/features/activity/imports_tab.dart`
- Create: `app/lib/features/activity/widgets/import_state_section.dart`
- Create: `app/lib/features/activity/widgets/import_row.dart`
- Reuse: `activity_archive_provider` (scoped per-entity for imports vs activities)
- Tests: `app/test/features/activity/imports_tab_test.dart`, `app/test/features/activity/widgets/import_row_test.dart`

---

## Story ahr-5: Flutter — "See all" footer

As Leo,
I want a "See all" section at the bottom of the Imports tab that I can tap to reveal archived imports and anything older than 30 days,
so that I can find things I dismissed earlier without having them clutter my main view.

### Acceptance Criteria

1. `SeeAllFooter` widget renders at the bottom of `ImportsTab`, below all four state sections.
2. Collapsed state: a single row with "See all (N) ›" where N is the count of archived + >30d-completed imports. Caret rotates on tap.
3. Expanded state: a list of `ImportRow`s for archived + >30d-completed items, sorted by archive timestamp DESC then `created_at DESC`. Muting applied via a theme-aware token: `textColor = colorScheme.onSurface.withOpacity(0.65)`, not raw `Opacity(0.65)` on the widget tree, so dark mode stays legible.
4. Data fetched lazily — only on expand. Subsequent expand/collapse toggles don't refetch within the session.
5. **Swipe-right-to-unarchive** on See-all rows: swipe-right fires `POST /v1/import-items/{id}/unarchive` (or `POST /v1/user-activities/{id}/unarchive`), optimistic with 3s undo. Row disappears from See-all and re-enters its color section based on current status. Archived items whose status is now in-progress (re-entered the pipeline) unarchive back into the In Progress section. (Answer to the workshop's "unarchive-by-swipe" escalation: yes, symmetric with archive-swipe.)
6. If N = 0, the See-all footer is not rendered at all.
7. Uses `?include_archived=true&archived_only=true` on the list endpoints (or, alternatively, two parallel fetches: one for `archived_only=true`, one for `status=completed&before=<30d-ago>`).
8. **Archived item that flips status server-side stays archived.** If a webhook updates an archived item from `awaiting_review` → `failed` while archived, the next poll returns it with the new status AND `archived_at IS NOT NULL`. It remains in See-all until the user explicitly unarchives. (Prevents a noisy reshuffle where the user thought they were done with it.)
9. Integration test: seed 2 archived + 1 completed-35d-ago items → See-all row reads "See all (3)"; expand → all three rendered muted.
10. Unarchive test: seed an archived yellow item; open See-all; swipe-right; assert row moves to Needs Review section; tap undo within 3s; assert row returns to See-all.

### Key Files

- Create: `app/lib/features/activity/widgets/see_all_footer.dart`
- Tests: `app/test/features/activity/widgets/see_all_footer_test.dart`

---

## Story ahr-6: Flutter — `ImportStateColors` theme extension + audit

As Leo (indirectly, via code-quality),
I want all import-state colors to go through a single theme extension so a color change lands in one place,
so that the app never drifts into mismatched color semantics across screens.

### Acceptance Criteria

1. New `ImportStateColors` extends `ThemeExtension<ImportStateColors>` with four `Color` fields: `inProgress`, `needsReview`, `failed`, `autoImported`. (Token names are **locked** — no renames, no new variants like `dismissed`/`archived` — those are states, not colors.)
2. Wired into `ThemeData.extensions` for both light and dark theme.
3. **WCAG AA contrast:** chip text on chip background passes a ≥4.5:1 contrast ratio in both light and dark themes. This is asserted as a widget test that pumps each state chip with both theme brightnesses and runs `WCAGContrastMatcher.meetsAA()` (or equivalent).
4. Audit: every file in `app/lib/features/activity/` and `app/lib/features/recipes/add_recipe/` that previously referenced `colorScheme.primary/.tertiary/.error/.secondary` for import-state purposes is migrated to the new extension. The audit list lives in the story's implementation notes.
5. Unchanged: non-import color references (general theme colors, buttons, text) stay on `colorScheme`.
6. `ImportActivityDetail` + `LiveImportStrip` + `ImportStateSection` + `ImportRow` all read colors from the extension.
7. Widget test: pump each of the above widgets with a stub theme extension and assert the rendered chip/background color matches the token value.

### Key Files

- Create: `app/lib/theme/import_state_colors.dart`
- Modify: `app/lib/theme/app_theme.dart` (wire extension)
- Modify: `app/lib/features/activity/widgets/import_activity_detail.dart`
- Modify: `app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart`
- Modify: `app/lib/features/activity/widgets/import_row.dart`, `import_state_section.dart`
- Tests: `app/test/theme/import_state_colors_test.dart`

---

## Story ahr-7: Retire `/activity/import-history` route + final regression audit

As Leo,
I want the old `/activity/import-history` route and its filter-chip redirect to be cleanly retired,
so that there's only one place the Imports view lives and old deep links don't 404.

### Acceptance Criteria

1. `app_router.dart` no longer registers `/activity/import-history`. Any navigation to that path is router-intercepted and rewritten to `/activity?tab=imports` — the redirect fires for both in-app nav AND initial-route handling on cold-start.
2. `ImportHistoryScreen` widget file is NOT deleted yet (per PRD out-of-scope — one-release deprecation lap). A `@Deprecated` annotation is added to the class with a note referencing this epic.
3. `LiveImportStrip` deep-link updates from `/activity?filter=imports` to `/activity?tab=imports`.
4. Grep audit: no source file outside of `activity/` features references `/activity/import-history` or `?filter=imports`. Any stragglers (e.g., notification payloads, push-notification handlers) are updated.
5. **Automated regression coverage** (no "manually verified" checkboxes):
    - Golden test for the home notification bubble rendering with a seeded unread count.
    - Widget test for the bottom-nav Activity badge showing the correct count formula (unread notifications + actionable imports; green excluded).
    - Router test simulating a cold-start initial URL of `/activity/import-history` (as if from a historical push payload) → asserts final resolved route is `/activity?tab=imports`.
    - Integration test: simulate push tap while the app is running → assert router rewrite works in-flight as well.
6. Cross-tab state test: seed 1 unread notification + 3 actionable imports. Open Imports first, back out, open Notifications. Assert the two tabs' unread counts are independent (archiving an import does NOT decrement the notifications unread count).

### Key Files

- Modify: `app/lib/core/router/app_router.dart`
- Modify: `app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart`
- Add: `@Deprecated` marker on `app/lib/features/activity/import_history_screen.dart`
- Tests: `app/test/core/router/app_router_test.dart`

---

## Dependencies

- **Backend → Frontend:** ahr-1 must ship before ahr-3 / ahr-4 / ahr-5 (endpoint contracts).
- **Cross-epic:** `epic-import-row-rich-detail` depends on this epic's `ImportRow` widget landing (caret expansion embeds inside it).
- **Cross-cutting:** `epic-review-import-ingredient-polish` is independent and can parallel-ship.
- **No merge-freeze collision** with `epic-bugs-import-photo-pipeline` (different files) or `epic-calendars-sharing` (different features).

## Open Questions for the User

None required to start — all six asked-and-answered decisions from the 2026-04-18 batch pin the scope. Workshop (Phase 6) may surface edge cases; those get escalated before Story ahr-4 (biggest story) begins.

## Definition of Done (Epic Level)

- Leo opens `/activity`, sees two tabs, taps Imports, sees four color-coded sections sorted most-recent-first with counts, no empty sections rendered.
- Every non-blue row is swipeable to archive with 3s undo. Blue rows are read-only.
- Archived + >30d items accessible via "See all" footer in muted type.
- `LiveImportStrip` on Add Recipe deep-links to `/activity?tab=imports`.
- `/activity/import-history` route is gone; deep links redirect. Legacy `?filter=imports` maps to `?tab=imports`.
- `ImportStateColors` theme extension is the single source for blue/yellow/red/green across every import-related screen.
- No regressions in home notification bubble, bottom-nav badge, or push deep-links.
- No backend changes beyond the archive columns + endpoints; `bugs-act-2a-backend-fields-addendum` work stays for the next epic.
