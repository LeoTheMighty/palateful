# Story iOS.5: Interactive Shopping List Widget (iOS 17+)

Status: done

## Story

As a user,
I want to check off shopping list items directly from my home screen widget,
so that I can mark items as bought at the grocery store without opening the app.

## Acceptance Criteria

1. Shopping List medium widget (from Story 3) shows checkboxes next to each item on iOS 17+
2. Tapping a checkbox marks the item as checked and updates the widget immediately
3. Checked items sync to the backend (shopping list API)
4. Widget visually updates: checked items show strikethrough and fade
5. On iOS 16 and below: widget shows items without checkboxes (read-only, graceful degradation)
6. Offline handling: if sync fails, queue the check and retry when online
7. Syncs with the Flutter app: if item is checked in widget, it shows checked when app is opened

## Tasks / Subtasks

- [x] Task 1: Define App Intents for shopping actions (AC: #2, #3)
  - [x] Create `ToggleShoppingItemIntent` App Intent in native Swift
  - [x] Parameters: `itemId: String`, `listId: String`, `checked: Bool`
  - [x] `perform()`: update UserDefaults immediately (for instant widget update) + make API call to backend
  - [x] API call: `PUT /shopping-lists/{listId}/items/{itemId}` with checked status
  - [x] Handle auth: store API token in Keychain accessible by App Group

- [x] Task 2: SwiftUI — Interactive shopping widget (AC: #1, #4, #5)
  - [x] Wrap checkbox interaction with `@available(iOS 17.0, *)` check
  - [x] Each item row: `Button(intent: ToggleShoppingItemIntent(itemId: item.id)) { ... }`
  - [x] Checked state: strikethrough text + reduced opacity
  - [x] On iOS 16: same layout but without `Button` wrapper (static display)

- [x] Task 3: Backend sync from widget (AC: #3, #6)
  - [x] Store API auth token in shared Keychain (accessible by both app and widget extension)
  - [x] `ToggleShoppingItemIntent.perform()` makes direct HTTP call to API
  - [x] On failure: write pending changes to UserDefaults queue
  - [x] Flutter app checks pending queue on launch and syncs

- [x] Task 4: Flutter — Sync state on app open (AC: #7)
  - [x] On app resume: check UserDefaults for widget-originated changes
  - [x] Reconcile with local state
  - [x] Clear pending queue after successful sync

## Dev Notes

- Interactive widgets require iOS 17+ and App Intents framework
- The App Intent runs in the widget extension process, not the Flutter app — it needs to make API calls independently
- Auth token sharing via Keychain with App Group access is the standard pattern
- Keep the widget responsive: update UserDefaults immediately for visual feedback, sync to backend async
- The `perform()` method in the App Intent must return quickly — do API call in background
- Test offline scenarios: check items while in airplane mode, verify sync when back online

### References

- [Investigation: 09-ios-native-features.md — Interactive Widgets section]
- [Epic: epic-ios-native.md]
