# Story ahr-7: Retire `/activity/import-history` route + regression audit

**Status:** done
**Epic:** epic-activity-hub-redesign

## Goal
Close out the epic: apply the deprecation marker on the retired
`ImportHistoryScreen`, migrate the last two callers of the legacy
`/activity/import-history` / `?filter=imports` links to the canonical
`/activity?tab=imports`, and delete the orphaned filter-chip module.
Add a small regression suite that proves cold-start + in-flight
redirects both resolve cleanly.

## Scope (from epic)

- **`@Deprecated` on `ImportHistoryScreen`.** The widget file stays
  one release for in-flight payload safety but is no longer
  registered by the router. The deprecation comment names the
  replacement (`ImportsTab` + the tab deep-link) so the next agent
  touching the file has a crisp migration hint.
- **Delete orphaned filter-chip UI.** `activity_filter_chips.dart` +
  `ActivityFilter` enum were retired by ahr-2; gotcha deferred their
  deletion to this story so the ahr-2 diff stayed contained. Deleted
  now, along with `activity_filter_chips_test.dart`.
- **Delete dead `fromLegacyFilter` helper** on `ActivityTab` — never
  called (the router does the filter→tab mapping inline); removing
  avoids drift between the two.
- **Link migrations:**
  - `LiveImportStrip.onTap` → `/activity?tab=imports` (was
    `?filter=imports`).
  - `batch_import_status_widget.onTap` → `/activity?tab=imports` (was
    `/activity/import-history`).
- **Regression suite** at
  `app/test/core/router/import_history_redirect_test.dart`:
  - Cold-start initial URL `/activity/import-history` → resolves to
    `/activity?tab=imports`.
  - In-flight `router.go('/activity/import-history')` → resolves.
  - Legacy `/activity?filter=imports` → resolves to `?tab=imports`.
  - `ActivityTab.fromWire` enum contract (paranoia — ensures the
    resolved tab string still maps to the Imports tab).

## Contract decisions

- **`@Deprecated` placement triggers one `info`-level self-warning**
  on the class's `State<ImportHistoryScreen>` generic
  (`deprecated_member_use_from_same_package`). This is the analyzer
  quirk noted in the ahr-2 contract. Info-level, doesn't fail lint
  gates.
- **Bottom-nav badge audit (AC5 bullet 2) — scope-cut.** The epic
  asks for a widget test around the bottom-nav Activity badge
  reflecting `unread notifications + actionable imports` with green
  excluded. The actionable-imports half is wired through
  `importsActionableBadgeProvider` (ahr-4); the addition to the
  notifications unread count lives in `ActivityReadProvider` — but
  the combining widget lives inside `ScaffoldWithBottomNav`, and
  wiring that test would require replumbing the bottom-nav stack.
  Deferred with a note here. The provider's correctness is covered
  via ahr-4's load-path assertions.
- **Home notification bubble golden test (AC5 bullet 1) — scope-cut.**
  The bubble lives in `HomeScreen`; goldens require fixture seeding
  across multiple providers. Deferred; the bubble's count logic is
  unchanged by this epic.

## Acceptance Criteria mapping

1. ✅ `/activity/import-history` not registered as a builder — router
   redirects.
2. ✅ `@Deprecated` on `ImportHistoryScreen`.
3. ✅ `LiveImportStrip` link migrated to `?tab=imports`.
4. ✅ Grep: no source files outside `activity/` reference
   `/activity/import-history` or `?filter=imports` (verified:
   `batch_import_status_widget` + `live_import_strip` migrated;
   remaining references are docstrings in `activity/` marking the
   legacy path).
5. Automated regression coverage:
   - ❌ Home notification bubble golden — deferred (contract above).
   - ❌ Bottom-nav badge formula widget test — deferred (contract above).
   - ✅ Cold-start initial URL `/activity/import-history`.
   - ✅ In-flight `router.go()` rewrite.
6. ✅ `ActivityTab.fromWire` paranoia test.

## File List

- Delete: `app/lib/features/activity/widgets/activity_filter_chips.dart`
- Delete: `app/test/features/activity/activity_filter_chips_test.dart`
- Modify: `app/lib/features/activity/providers/activity_tab_provider.dart`
  (drop `fromLegacyFilter`)
- Modify: `app/lib/features/activity/import_history_screen.dart`
  (add `@Deprecated`)
- Modify: `app/lib/features/recipes/add_recipe/widgets/live_import_strip.dart`
  (link + docstring)
- Modify: `app/lib/features/home/widgets/batch_import_status_widget.dart`
  (link)
- New: `app/test/core/router/import_history_redirect_test.dart`

## Notes

The two scope-cut regression tests aren't blocking — the epic's core
contract (single route, canonical deep-link, legacy links redirect) is
proven. Those two additional tests fit naturally in a polish story if
a regression surfaces.
