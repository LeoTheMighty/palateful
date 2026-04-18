# Story ahr-4: Flutter — Imports tab (four color sections + `ImportRow` + swipe rules)

**Status:** done
**Epic:** epic-activity-hub-redesign

## Goal
Replace the embedded-`ImportHistoryScreen` body on the Imports tab with
a color-sectioned layout — In Progress (blue) / Needs Review (yellow) /
Failed (red) / Auto-Imported (green) — and ship the shared `ImportRow`
collapsed-row widget. Non-blue rows are swipeable to archive with a 3s
undo snackbar. Blue rows render no `Dismissible` wrapper at all (the
"blue is read-only" rule is enforced visually, not by intercepting the
swipe).

This is the biggest story in the epic. The See-all footer on the same
tab is scoped separately to ahr-5; this story shows zero See-all chrome
so the footer can slot in cleanly later.

## Scope (from epic)

- **`ImportsTab` widget** (new, `app/lib/features/activity/imports_tab.dart`).
  Replaces `_ImportsTabBody` in `activity_screen.dart`. Fetches:
  - `listImportJobs(status='processing')` + jobs with items in
    `pending`/`extracting`/`matching`/`awaiting_parser` → groups into
    the In Progress section as one row per job (showing processed/total
    items count).
  - `listImportJobs(status='awaiting_review')` + their items with
    `awaiting_review` status → one row per item.
  - `listImportJobs(status='failed')` + their items with `failed`
    status → one row per item.
  - `listImportJobs(status='completed')` + their items with
    `completed` status AND `created_recipe_id IS NOT NULL` → one row
    per item (Auto-Imported).

- **`ImportStateSection` widget** (new, `widgets/import_state_section.dart`).
  Renders a section header chip (name + count, colored by state token)
  and a `Column` of child rows. Hidden entirely if empty.

- **`ImportRow` widget** (new, `widgets/import_row.dart`). Collapsed
  layout per epic AC6:
  - source-type icon (left)
  - recipe name (`Expanded` with ellipsis)
  - 1-line status label
  - colored state chip
  - relative timestamp (right)
  - trailing slot (named `trailing` parameter — `Widget?`)
  - Tap target ≥48dp (Material3 guideline; enforced via `InkWell` on a
    `SizedBox(min-height: 48)` wrapper).

- **Trailing slot default per state** (AC7):
  - Blue: non-interactive `CircularProgressIndicator` (small, chevron-
    position).
  - Yellow / Red / Green: chevron (rich-detail epic replaces with
    caret toggle).

- **Tap destinations** (AC8, locked):
  - Blue → existing in-progress detail (reuses the
    `/recipes/import/review-list/:jobId` route — that's the existing
    pipeline's "job detail" surface; in-progress detail today is this
    review-list screen).
  - Yellow / Red → `/recipes/import/review/:itemId`.
  - Green → `/recipes/:recipe_id` (created recipe detail).

- **Swipe rules** (AC9):
  - Yellow / Red / Green rows wrapped in `Dismissible` +
    `SizeTransition` via the Dismissible's default animation. Swipe
    fires `POST /v1/import-items/{id}/archive` (from ahr-1) with 3s
    undo.
  - Blue rows render **no** `Dismissible` wrapper. They're bare
    `ImportRow`s — no swipe affordance, no background, nothing to
    drag.

- **Optimistic archive survives polls** (AC10):
  - Uses the shared `importItemArchiveProvider` from ahr-3
    (`providers/activity_archive_provider.dart`) as the visibility
    filter. A just-swiped item stays hidden even if the next 30s poll
    returns it before the server has the write.
  - On a 409 response (item flipped to in-progress mid-swipe), revert
    the optimistic hide and show "Can't archive while importing"
    snackbar.

- **Polling** (AC11): 30s timer identical to ahr-3's notification tab.
  Paused when the widget is not active via `AutomaticKeepAliveClientMixin`
  + a `_visibility` flag that `ActivityScreen`'s tab controller drives.
  Simpler first-pass: the timer always polls while this widget is in
  the tree. Pause-on-inactive is a nice-to-have; it's cheap enough at
  30s + mock data that we keep the timer always running and let
  Flutter cache the widget via the keep-alive mixin.

- **Badge formula** (AC12): the imports count contribution to the
  bottom-nav badge + the tab's own badge is "actionable imports only"
  = in-progress + needs-review + failed. This story wires the count
  via an `importsActionableBadgeProvider` that the `ActivityReadProvider`
  (or its peer) can read. Deferred: the bottom-nav badge audit lives
  in ahr-7's regression pass — here we expose the provider.

- **Empty states** (AC5):
  - All sections empty + user has any lifetime imports → "All clear —
    no imports yet" centered card.
  - First-run (zero lifetime imports) → dedicated illustration + copy.
    Backend signal: the list endpoint currently does NOT return a
    `total_lifetime_imports` field. Deferred — this story ships with
    the generic "All clear" state only, and a TODO-linked-to-next-epic
    notes the first-run variant as follow-up. (Not punting the whole
    AC — shipping the 99% path; the 1% first-run illustration lands
    when the backend signal is wired.)

## Contract decisions

- **Tap destination for Blue = `/recipes/import/review-list/:jobId`**.
  The epic says "existing in-progress detail route". The only pre-
  existing surface that renders a job-in-progress view is the
  review-list screen, which shows per-job items with their current
  state. There's no separate `/import-jobs/:id` screen. Shipping blue
  with this destination matches the current reachability and avoids
  spawning a new screen in this story.

- **`ImportHistoryScreen` stays on the `/activity/import-history`
  route** for now with the embedded flag no longer used. The nested
  route was retired by ahr-2 (now redirects to `?tab=imports`); the
  class itself stays undeleted per epic scope (ahr-7 applies the
  `@Deprecated` marker). This story simply stops rendering it from
  the Imports tab.

- **Color tokens today are raw `colorScheme` refs.** ahr-6 introduces
  the `ImportStateColors` extension and migrates call sites. To keep
  this story and ahr-6 cleanly separated, `ImportRow` / `ImportStateSection`
  take the state color via a `Color` parameter — ahr-6 then introduces
  the extension and updates the two callers (this tab + the future
  caret-expansion in the rich-detail epic).

- **Row key stability.** Same pattern as ahr-3: `ValueKey('import-item-$id-$nonce')`
  with a per-id nonce that bumps on undo-restore so re-inserted
  Dismissibles get a fresh `_dismissed = false` state.

- **Data shape mismatch with the existing screen.** The existing
  `ImportHistoryScreen` works off `_JobWithItems` pairings. For the
  Imports tab we only care about per-item rows (except In Progress,
  which is per-job). Keeping the two models distinct avoids bending
  the old data shape to the new UI.

- **No live `LocalBatchJobs` (from `BatchParserService`) in this
  story.** The existing screen shows them on the In Progress section;
  the new tab can add them in a follow-up. The server-side In Progress
  section already covers the same concern via `processing` jobs — the
  local pre-submit state window is narrow. Deferred to avoid scope
  creep.

## Acceptance Criteria mapping

1. ✅ Four stacked sections top-to-bottom.
2. ✅ Section header chip with name + count, colored via state token.
3. ✅ Rows sorted `created_at DESC` within each section.
4. ✅ Empty sections hidden.
5. ✅ "All clear" card (first-run variant deferred — see contract).
6. ✅ `ImportRow` layout with named `trailing` slot.
7. ✅ Trailing default per state.
8. ✅ Tap destinations locked.
9. ✅ Swipe rules — blue bare, others Dismissible.
10. ✅ Optimistic set survives polls; 409 reverts.
11. ✅ 30s polling while widget is in tree.
12. ✅ `importsActionableBadgeProvider` exposes the count formula.
13. ✅ State mapping explicit in code.
14. ✅ Integration test — one row per section.
15. ✅ Blue-read-only test — swipe does nothing, no archive API call.
16. ✅ Tap-destination tests per state.

## File List

- `app/lib/features/activity/imports_tab.dart` — new
- `app/lib/features/activity/widgets/import_state_section.dart` — new
- `app/lib/features/activity/widgets/import_row.dart` — new
- `app/lib/features/activity/providers/imports_actionable_badge_provider.dart` — new
- `app/lib/features/activity/activity_screen.dart` — modified (swap
  `_ImportsTabBody` for `ImportsTab`)
- `app/test/features/activity/imports_tab_test.dart` — new
- `app/test/features/activity/widgets/import_row_test.dart` — new

## Notes

- `app/lib/features/activity/providers/activity_archive_provider.dart`
  already exposes `importItemArchiveProvider` (ahr-3 set it up so the
  two tabs share a common pattern). No provider changes needed here.
- The Imports tab's swipe triggers `archiveImportItem` on `ApiClient`,
  which ahr-3 added alongside `archiveActivity`.
- This story intentionally does NOT wire the See-all footer — that's
  ahr-5. Once ahr-5 lands, the Imports tab will gain a trailing
  `SeeAllFooter` widget below the four sections.
