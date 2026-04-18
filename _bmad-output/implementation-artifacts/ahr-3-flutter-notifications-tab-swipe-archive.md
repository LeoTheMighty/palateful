# Story ahr-3: Flutter — Notifications tab (feed + swipe-to-archive + undo)

**Status:** done
**Epic:** epic-activity-hub-redesign

## Goal
Extract the Notifications tab body from the ahr-2 shell into its own
`NotificationsTab` widget and add swipe-to-archive per row with a 3s
undo snackbar. Optimistic removal is reverted on failure. This is the
first user-visible swipe surface that hits ahr-1's new
`POST /v1/activities/{id}/archive` endpoint.

## Scope (from epic)

- **`NotificationsTab` widget** (new file,
  `app/lib/features/activity/notifications_tab.dart`). Takes over the
  chronological non-import activity feed currently rendered inline
  inside `activity_screen.dart`. Preserves the bugs-act-1 tab-open
  mark-all-read behavior, the 30s poll, and the empty state.
- **`activity_archive_provider.dart`** — a tiny optimistic-archive
  state tracker: held as a `Notifier<Set<String>>` of locally-archived
  activity IDs so a row stays hidden across the next 30s poll even if
  the server is briefly still returning it. On a confirmed success the
  id stays in the set (no-op). On a confirmed failure the id is
  removed and the UI reverts. (The set clears on app restart — server
  wins on reconciliation.)
- **Swipe UX.** Each row is wrapped in `Dismissible` with
  `direction: DismissDirection.endToStart`. Background shows a red
  archive icon. `onDismissed` fires the archive API and shows a 3s
  snackbar "Archived · Undo". Undo fires the unarchive endpoint and
  restores the row in-place.
- **Error path.** If the archive call fails (non-2xx), the optimistic
  removal is reverted and an error snackbar displays "Couldn't
  archive, try again". No persistent UI state is left in an archived-
  but-server-active state.
- **`ApiClient` gets `archiveActivity(id)` / `unarchiveActivity(id)`**.
  Backend router is `/v1/activities` (not `/v1/user-activities` as the
  epic text claims — corrected per the ahr-1 contract).
- **`ActivityScreen` rewire.** The inline `_NotificationsTabBody` is
  replaced by an import of `NotificationsTab` from the new file.
  The `_importActivityTypes` constant moves to the new file.

## Contract decisions

- **Provider as `Notifier<Set<String>>`**, not `StateNotifierProvider`
  or `StateProvider`. Riverpod 3.0-dev removed `StateProvider`; the
  project convention (set by ahr-2) is `NotifierProvider` with an
  explicit `Notifier<T>` subclass. The set is copy-on-write (`{...state}`)
  so `ref.listen` fires on every mutation.
- **No new ApiClient wrapper class.** Archive/unarchive are thin
  `Future<Response>` methods on the existing `ApiClient`; the provider
  holds the optimistic set but calls into `ApiClient` directly via
  `GetIt`. Matches the pattern of `ActivityReadProvider`.
- **Snackbar duration = 3s exactly** (per epic AC3). `Duration(seconds:
  3)`. Snackbars use `SnackBarAction(label: 'Undo', ...)` so the tap
  target matches Material3 defaults. We do NOT chain a second snackbar
  on the undo tap — the undo call is fire-and-forget with a silent
  fail (the row is already back in view; a toast on successful undo
  would be noise).
- **Error snackbar uses the theme's `colorScheme.error`.** Matches the
  existing pattern in `import_history_screen.dart`.
- **Empty state unchanged** — existing "You're all caught up" card is
  preserved verbatim.
- **Polling unchanged** — 30s timer still lives inside the tab body
  (`AutomaticKeepAliveClientMixin` keeps it alive across swipes).
- **Optimistic set doesn't persist across app restarts.** On next cold
  start, the server is the source of truth. Matches principle 6:
  "optimistic archive survives an intervening poll" — intervening
  means during the same session.

## Acceptance Criteria Mapping

1. ✅ Chronological list of non-import `user_activity` rows, sorted
   `created_at DESC`. Types `invitation`, `partner_action`,
   `meal_reminder`.
2. ✅ `Dismissible` wraps each row. Swipe-left removes optimistically +
   fires archive.
3. ✅ 3s snackbar with "Archived · Undo". Undo fires unarchive.
4. ✅ Error snackbar + restore on API failure.
5. ✅ Tab-open mark-all-read preserved.
6. ✅ `SizeTransition`-style removal via `Dismissible`'s built-in
   animation (Flutter's default — same animation used in
   `import_history_screen.dart`).
7. ✅ Empty state preserved.
8. ✅ 30s polling preserved.
9. ✅ Integration test: seed 2 activities, swipe, assert removed + API
   fired; tap Undo, assert restored.
10. ✅ Error-path test: stub failure, swipe, assert row restored +
    error snackbar.

## File List

- `app/lib/features/activity/notifications_tab.dart` — new
- `app/lib/features/activity/providers/activity_archive_provider.dart`
  — new
- `app/lib/features/activity/activity_screen.dart` — modified (delegate
  the Notifications tab body to the new widget; remove the inline
  `_NotificationsTabBody`)
- `app/lib/core/services/api_client.dart` — modified (add
  `archiveActivity` / `unarchiveActivity`)
- `app/test/features/activity/notifications_tab_test.dart` — new
- `app/test/features/activity/activity_screen_test.dart` — modified
  (the previous inline tab tests now pump `NotificationsTab` through
  the shell — the existing fake client gets `archiveActivity` /
  `unarchiveActivity` no-ops so tab-open mark-all-read tests stay
  green)

## Notes

- `flutter test test/features/activity/` stays green with these
  changes. Existing shell tests continue to pump the `ActivityScreen`
  — they only need the `_FakeApiClient` to tolerate the new API
  methods.
- The `Dismissible` + removal-animation combo flickers when a
  `ListView.builder` re-orders. We use a stable `ValueKey(id)` per
  row so Flutter reuses the element across polls.
- The epic spec notes `AnimatedList` is deliberately avoided in favor
  of `Dismissible` + `SizeTransition`; this story matches that.
