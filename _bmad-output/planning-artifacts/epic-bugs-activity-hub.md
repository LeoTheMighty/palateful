<!-- refined via party-mode 2026-04-16 -->
# Epic: Activity Hub Polish — Finish What Epic 13 Started

## Overview

Epic 13 and MVP Finalization wired up the Activity Hub: the feed polls every 30s, there's a `MarkActivityRead` endpoint, import activities have a dedicated detail screen, and the backend tracks unread counts. But Leo's daily use still surfaces three real bugs:

1. Notifications show "unread" every time the screen is opened, even after tapping through them.
2. The import activity detail view is missing fields — there's data the backend returns that the UI doesn't render.
3. The "In Progress / Import History" row inside the Add Recipe screen is a duplicate surface. Leo wants one place (Activity Hub) to track pipeline state.

None of these are architectural rewrites — they are bugs and UX consolidation on existing infrastructure.

**Goal:** After this epic, opening the Activity tab once clears the badge and it stays cleared across cold starts, every import activity row shows everything the backend knows about it, and the Add Recipe screen no longer owns pipeline-state UI.

## Design Principles (refined via party-mode 2026-04-16)

1. **Tab-open marks all loaded items read** (Quinn+John) — no viewport tracking in v1. Simple behavior Leo understands beats correct behavior he doesn't. Revisit only if over-eager marking becomes a complaint.
2. **Server wins on cold-start reconciliation** — optimistic local read state bows to authoritative server state when they diverge. A brief flash of unread after cold start is acceptable.
3. **Hierarchical render of import-detail fields** (Sally) — one opinionated layout: error → stage → source → timestamps → retry history. Not a dump-all-fields grid.
4. **Field-render policy** (Quinn) — every backend-returned field is either rendered or annotated in code as intentionally-not-shown. No silent drops.
5. **Missing backend fields → follow-up story, not widened scope** (Winston+Bob) — the field audit in bugs-act-2 can surface gaps, but they spawn a new story, not expand this one.
6. **Ambient links survive rehoming** (Sally) — a slim live-progress strip stays on Add Recipe after bugs-act-3 rehomes the full list. It's a link, not a duplicate.
7. **Constructive actions don't get snackbar-undo** — approve, schedule, add. Locked decision #3 from workshop 1 applies only to destructive ops.

## Inherited Locked Decisions (from workshop 1)

- No feature flags, no backwards-compat shims.
- Admin-only gates live on `is_admin`.
- Destructive user actions use snackbar-undo (3s).
- Audit-log all admin-invoked mutations.
- Idempotent writes over wider transactions.
- Directories: ops scripts → `services/api/scripts/`; migrations → `services/migrator/migrations/`; Flutter feature subdirs → `app/lib/features/<area>/widgets/`.
- No stories for capabilities without a named user ask.

## File Structure (expected)

```
app/lib/features/activity/
├── activity_screen.dart                   # MODIFIED — mark-read on tab open + cold-start reconcile
├── providers/activity_read_provider.dart  # NEW — local read-state cache + optimistic + reconcile
└── widgets/
    ├── import_activity_detail.dart        # MODIFIED — hierarchical render (error → stage → source → time → retry)
    └── activity_filter_chips.dart         # NEW — filter enum: all | imports | partner | reminders

app/lib/features/add_recipe/
├── add_recipe_screen.dart                 # MODIFIED — remove in-progress list, add ambient live-progress strip
└── widgets/
    └── live_import_strip.dart             # EXTRACTED — slim ambient indicator, links to Activity Hub

app/lib/core/router/app_router.dart        # MODIFIED — /activity?filter=<enum> query param

services/api/src/api/v1/user_activity/
└── mark_activity_read.py                  # AUDIT — confirm idempotency (read changes)
```

## Story Map

| # | Story | Priority | Est. Effort | Dependencies |
|---|-------|----------|-------------|--------------|
| bugs-act-1 | Fix persistent-unread: tab-open marks loaded, cold-start reconciles | 🔴 P0 | 1 d | None |
| bugs-act-2 | Hierarchical render of import-detail fields + field audit | 🟡 P1 | 0.5 d | None (parallel) |
| bugs-act-3 | Move Add Recipe in-progress list to Activity Hub + ambient strip | 🟡 P1 | 0.5–1 d | bugs-act-1 (shared activity screen changes) |

**Total estimated effort: 2–2.5 days**

---

## Story bugs-act-1: Fix persistent-unread bug

As Leo,
I want notifications to stay marked as read after I've seen them, across app restarts and polling refreshes,
so that I can trust the unread badge.

### Acceptance Criteria

1. **Outcome AC:** After opening the Activity tab, the unread count is 0 and remains 0 across: tab navigation, app background/foreground, cold restart, and the next 30s poll refresh.
2. On Activity tab open, every currently-loaded activity item is marked read. No viewport/intersection tracking — all loaded items.
3. Read state is marked optimistically on the client — UI updates without waiting for the server. A failed server write is logged (not surfaced to user) and retried up to 2 times with exponential backoff.
4. **Cold-start reconciliation:** on app launch, if the client's local read state diverges from the server's authoritative state, server wins. A brief flash of unread is acceptable; silent divergence is not.
5. Unread badge on bottom nav clears within 500ms of tab open.
6. Import-activity items (in `ImportActivityScreen`) follow the same "mark loaded on surface open" rule. If they use a separate endpoint, align behavior.
7. "Mark all as read" remains available from Activity tab overflow menu as a safety valve.
8. Integration test: seed two unread activities, open activity screen, assert subsequent poll returns both as `read=true` and unread count is 0 on the server.
9. Cold-start test: seed unread on server, cold-start the app with stale local read state, assert UI reflects server state (unread visible, then cleared on tab open).

### Key Files
- Modify: `app/lib/features/activity/activity_screen.dart`
- Create: `app/lib/features/activity/providers/activity_read_provider.dart`
- Audit: `services/api/src/api/v1/user_activity/mark_activity_read.py`, `mark_all_read.py` (confirm idempotency)
- Tests: `app/test/features/activity/` or `services/api/tests/api/v1/user_activity/`

---

## Story bugs-act-2: Hierarchical render of import-detail fields + field audit

As Leo,
I want the import activity detail view to show me the fields that matter most, in the order I need them, with nothing silently hidden,
so that I can diagnose failed imports without dropping into the database.

### Acceptance Criteria

1. **Field audit task:** produce a list in this story's implementation notes of every field the import-item response schema returns, mapped to one of three dispositions: `rendered`, `annotated-not-shown`, or `MISSING-needs-backend`. The list lives as a code comment block in `import_activity_detail.dart` header.
2. **Hierarchical render order** (top to bottom) when each field is present:
   - error message (if status is failed/error)
   - current stage + last successful stage
   - source (URL / text snippet / photo thumbnail)
   - created/updated timestamps
   - retry count + last retry timestamp
   - confidence score on extracted output (if applicable)
3. Error message collapses to a 2-line preview with a "Show more" disclosure. **Default: closed.**
4. Batch imports render per-item rows, each with its own stage+status. No job-level rollup that hides per-item state.
5. Source links are tappable: URL opens in browser, photo opens in image viewer, text expands inline.
6. **Scope gate:** if the audit reveals a backend field is missing and desirable (e.g., structured extraction confidence by section), a follow-up story is filed as `bugs-act-2a-backend-fields-addendum`. This story does not expand to include backend work.
7. Every field in the response schema is either rendered by this story or has a `# intentionally-not-shown: <reason>` annotation next to its disposition in the comment block.
8. Layout is a scrollable card, not a multi-page flow.

### Key Files
- Modify: `app/lib/features/activity/widgets/import_activity_detail.dart`
- Audit: `services/api/src/schemas/import_job.py`, `import_item.py` (produce field inventory)

---

## Story bugs-act-3: Move Add Recipe in-progress list to Activity Hub + ambient strip

As Leo,
I want pipeline state to live in the Activity Hub, with a slim ambient indicator on Add Recipe linking there,
so that I check one place for status but don't lose visibility when I'm actively importing.

### Acceptance Criteria

1. The "In Progress", "Recently Imported", and "Import History" sections on the Add Recipe screen are removed.
2. A slim ambient **live-progress strip** remains on Add Recipe: single row, shows count of currently-in-progress imports + a label ("2 imports in progress"), taps through to `/activity?filter=imports`. When no imports are active, the strip is not rendered (no empty state).
3. The Activity Hub gains a filter chip row: `all` (default) | `imports` | `partner` | `reminders`. Only chips that have matching activities are shown; `all` is always visible.
4. **Default filter** on Activity Hub open is `all`. `imports` is a destination reached via filter chip or deep link, not the default landing.
5. Deep-link schema: `/activity?filter=<enum>` where enum is `all | imports | partner | reminders`. **This schema is canonical** — future epics that add filter categories extend the enum, don't invent a new param.
6. Actions currently available on Add Recipe in-progress rows (retry, dismiss, approve) are preserved in the Activity Hub import-detail view. No action is lost.
7. Approve remains undo-free (constructive). Dismiss and retry-failed get snackbar-undo per locked decision #3.
8. **Pre-implementation audit:** identify every screen that reads live import state (home notification bubble, bottom-nav badge, any other surface). Confirm each continues to work after the source of truth moves. Document findings in the story.
9. Regression test: approve a pending import from the new Activity Hub location. Assert the recipe is created and the activity marks resolved.

### Key Files
- Modify: `app/lib/features/add_recipe/add_recipe_screen.dart`
- Create: `app/lib/features/add_recipe/widgets/live_import_strip.dart`
- Modify: `app/lib/features/activity/activity_screen.dart`
- Create: `app/lib/features/activity/widgets/activity_filter_chips.dart`
- Modify: `app/lib/core/router/app_router.dart` (add `filter` query param)

## Definition of Done (Epic Level)

- Leo opens the Activity tab, leaves, comes back, cold-starts the app — unread badge stays at 0.
- Every import activity detail view renders fields in a hierarchical, opinionated layout. No field is silently dropped; all are rendered or annotated.
- Add Recipe screen has no in-progress list, but keeps a slim live-progress strip that links to the Activity Hub.
- No backend schema changes shipped as part of this epic. Any missing backend fields are filed as follow-up stories.
