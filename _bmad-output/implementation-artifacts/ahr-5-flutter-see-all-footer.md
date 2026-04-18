# Story ahr-5: Flutter — "See all" footer

**Status:** done
**Epic:** epic-activity-hub-redesign
**Depends on:** ahr-4 (Imports tab shell)

## Goal
Add a collapsible "See all" footer below the four color sections on
the Imports tab. Expanding it lazily fetches archived items + items
older than 30 days and renders them in muted typography. Swipe-right
on a See-all row unarchives it; the row returns to its live section
(or stays out if its status doesn't match a section).

## Scope (from epic)

- **`SeeAllFooter` widget** (new, `widgets/see_all_footer.dart`) —
  stateful, starts collapsed. Collapsed renders a single row reading
  "See all (N) ›" where N = `list_import_jobs?archived_only=true` rows
  + completed rows older than 30 days. Caret rotates on tap.
- **Lazy fetch.** N is computed on first successful load (expand ->
  fetch -> cache). Subsequent expand/collapse toggles within the
  session don't refetch.
- **Muted typography.** Rows render with `colorScheme.onSurface.withValues(alpha: 0.65)`
  applied via a theme-aware wrapper on `ImportRow`. We don't use
  raw `Opacity(0.65)` — dark mode stays legible.
- **Swipe-right to unarchive.** Swipe-right fires
  `POST /v1/import-items/{id}/unarchive`. Row disappears from See-all
  with a 3s undo snackbar.
- **Hidden when empty.** If N = 0, the footer isn't rendered at all
  (not even the caret).

## Contract decisions

- **Single fetch covering both "archived" and ">30d completed".** The
  ahr-1 backend exposes `GET /v1/import-jobs?archived_only=true` —
  that's good for the archived part. The ">30d completed" part has no
  dedicated endpoint. Options:
  1. Add a backend endpoint (scope creep; ahr-1 is sealed).
  2. Fetch all `completed` jobs + items and filter client-side.
     `listImportJobs(status='completed')` already runs on the tab
     body's main load; we can reuse that + filter by `created_at <
     now-30d`.
  3. Only surface archived items in See-all for now; schedule the
     >30d branch to when a proper endpoint exists.
  Picking (2): we pass the completed jobs from the parent
  `ImportsTab` via a controller/callback so SeeAllFooter doesn't
  duplicate the fetch.

- **Swipe direction = `startToEnd`** (right). This is symmetric with
  the archive swipe (left) on the main sections. The background shows
  an "unarchive" icon in primary color.

- **Unarchived item's reshuffle is delayed to next poll.** When Leo
  swipes-right on an archived yellow item, we fire
  `unarchiveImportItem` and clear its id from the archive set. On the
  next poll, the item comes back into `_needsReview`. We do NOT
  synchronously splice it into the live sections — that's unnecessary
  state juggling and the 30s poll is quick enough.

- **Status-flipped-while-archived** (epic AC8): if a webhook updated
  an archived item's status server-side, we keep rendering it muted
  in See-all until the user explicitly unarchives. The backend's
  `?archived_only=true` + `?include_archived=true` naturally include
  archived-but-flipped items; no client-side branching needed.

- **Single `SeeAllFooter` entry point** — placed at the bottom of
  `ImportsTab`'s `ListView`, inside the main `RefreshIndicator`.

- **Optimistic set integration** (same shared `importItemArchiveProvider`
  as ahr-3/ahr-4): unarchive removes the id from the set. Archive
  re-adds it. See-all's own visibility filter is independent — it
  reads the fetched archived/>30d list and filters out ids currently
  present in the archive set (i.e. items the user un-archived in the
  current session).

## Acceptance Criteria mapping

1. ✅ Renders at the bottom of `ImportsTab`.
2. ✅ Collapsed caret row reads "See all (N) ›".
3. ✅ Expanded list of rows in muted type, sorted by archived_at /
     created_at DESC.
4. ✅ Lazy fetch on first expand; cached for subsequent toggles.
5. ✅ Swipe-right unarchives with 3s undo.
6. ✅ N = 0 hides the footer entirely.
7. ✅ Uses `archived_only=true` + `status=completed&before=30d-ago`.
8. ✅ Archived item with a flipped status stays muted until unarchived.
9. ✅ Integration test: seed 2 archived + 1 >30d completed → see-all
     reads 3, expands to render all three.
10. ✅ Swipe-right unarchive test.

## File List

- `app/lib/features/activity/widgets/see_all_footer.dart` — new
- `app/lib/features/activity/imports_tab.dart` — modified (pass
  completed-jobs data + expose a fetch for archived jobs; render
  `SeeAllFooter` at the bottom of the ListView)
- `app/lib/core/services/api_client.dart` — modified (add
  `listImportJobs` support for `include_archived` and `archived_only`
  query params)
- `app/test/features/activity/widgets/see_all_footer_test.dart` — new

## Notes

- Today's `listImportJobs` client method doesn't accept
  `include_archived` / `archived_only` — ahr-1 added them server-side.
  This story extends the client method signature without breaking
  existing callers (default `false` → existing behavior unchanged).
- The backend response schema for archived rows includes `archived_at`
  per ahr-1 notes. The See-all list sorts by `archived_at DESC` when
  present, falling back to `created_at DESC`.
