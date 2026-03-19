# Story 8.3: Check Off Items with Real-Time Sync

Status: done

## Story

As a user shopping at the store,
I want to check off shopping list items and have my partner see the updates live,
So that we don't double-buy when shopping separately.

## Acceptance Criteria

1. **Check triggers real-time sync** — Checking an item calls `PUT /v1/shopping-lists/{list_id}/items/{item_id}` with `is_checked: true`; the router broadcasts `item_checked` to all WebSocket subscribers; the partner's device updates within 1 second.
2. **Checked items move to COMPLETED section** — Checked items are separated from unchecked items under a "COMPLETED" section header with item count badge; unchecked items remain in the active list sorted by urgency.
3. **Uncheck restores item** — Tapping a checked item unchecks it (`is_checked: false`); item returns to the active unchecked section.
4. **Clear All Completed** — Tapping "Clear All" in the COMPLETED section header deletes all checked items and removes the COMPLETED section.
5. **Optimistic updates** — The UI updates instantly on tap (before server confirmation); on error the change is rolled back and an error snackbar is shown.
6. **Hide/Show Completed toggle** — The overflow menu has "Hide Completed" / "Show Completed" toggle that hides/shows the entire COMPLETED section.

## Tasks / Subtasks

- [x] Task 1: Add optimistic update to `_toggleItemChecked` (AC: 5)
  - [x] Apply `item.copyWith(isChecked: !item.isChecked)` to local state before awaiting
  - [x] On success, apply server-returned item (authoritative `checkedAt`, etc.)
  - [x] On error, rollback to original item and show snackbar

- [x] Task 2: Write backend tests for `UpdateShoppingListItem` check-off path (AC: 1, 3)
  - [x] Create `services/api/tests/test_check_off_items.py`
  - [x] Test: check item success — `is_checked` becomes true, `checked_at` set, `checked_by_user_id` set
  - [x] Test: uncheck item — `is_checked` becomes false, `checked_at` / `checked_by_user_id` cleared
  - [x] Test: 404 when item not found
  - [x] Test: 403 when user has no list access
  - [x] Test: `notify_item_checked` is called when item is checked
  - [x] Test: `notify_list_complete` is called when last item is checked

- [x] Task 3: Write Flutter widget tests for check-off UI (AC: 2, 3, 4, 5, 6)
  - [x] Create `app/test/features/shopping_cart/check_off_test.dart`
  - [x] `ShoppingListItemTile`: checked item renders with strikethrough text and filled checkbox
  - [x] `ShoppingListItemTile`: unchecked item renders with plain text and empty checkbox
  - [x] `ShoppingListItemTile`: tap triggers `onChecked` callback
  - [x] `ShoppingListScreen` (logic unit): optimistic update applies before server response
  - [x] `ShoppingListScreen` (logic unit): rollback restores item on error

## Dev Notes

### What is Already Implemented

The core check-off infrastructure is fully in place — this story adds **optimistic update** and **test coverage**:

**Backend (fully functional):**
- `UpdateShoppingListItem` (`services/api/src/api/v1/shopping_list/update_item.py`):
  - Handles `is_checked` param; sets `checked_by_user_id` and `checked_at` on check; clears them on uncheck
  - Calls `notify_item_checked()` and `notify_list_complete()` (from `api/v1/shopping_list/utils/notifications.py`)
  - Access check: owner OR `ShoppingListUser` with role `owner`/`editor`
- Router (`services/api/src/routers/v1/shopping_list_router.py`, line 145–164):
  - `PUT /shopping-lists/{list_id}/items/{item_id}` broadcasts `item_checked` when `is_checked` in params; `item_updated` otherwise

**Flutter service (fully functional):**
- `ShoppingCartService.toggleItemChecked()` (`app/lib/features/shopping_cart/services/shopping_cart_service.dart`, line 89–95):
  - Calls `PUT /v1/shopping-lists/{list_id}/items/{item_id}` with `{'is_checked': !item.isChecked}`
- WebSocket handler (`shopping_cart_service.dart`, line 215–220):
  - `item_checked` and `item_updated` both route to `_itemUpdatedController` → `onItemUpdated` stream

**Flutter UI (fully functional):**
- `ShoppingListScreen._toggleItemChecked()` (`app/lib/features/shopping_cart/screens/shopping_list_screen.dart`, line 128–140):
  - **Gap**: awaits server before updating UI — no optimistic update yet
- `ShoppingListScreen._buildItemList()` (line 373–498):
  - Splits into `unchecked` and `checked` lists; renders COMPLETED section when `checked.isNotEmpty && _showChecked`
  - "Clear All" TextButton calls `_clearCheckedItems()` which deletes each checked item
  - Overflow menu toggles `_showChecked`
- `ShoppingListItemTile` (`app/lib/features/shopping_cart/widgets/shopping_list_item_tile.dart`):
  - Animated checkbox (green fill when checked), strikethrough text, faded color

### Optimistic Update Implementation

Modify `_toggleItemChecked` in `ShoppingListScreen`:

```dart
Future<void> _toggleItemChecked(ShoppingListItem item) async {
  HapticFeedback.lightImpact();
  // Optimistic update
  final optimistic = item.copyWith(isChecked: !item.isChecked);
  _handleItemUpdated(optimistic);
  try {
    final updated = await _service.toggleItemChecked(_list!.id, item);
    _handleItemUpdated(updated);
  } catch (e) {
    // Rollback
    _handleItemUpdated(item);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to update item')),
      );
    }
  }
}
```

### Backend Test Pattern

Follows the same pattern as `test_shopping_list_router_broadcasts.py` and `test_populate_from_recipe.py`. Key setup:
- `MockShoppingListItem(id=item_id, shopping_list_id=list_id, is_checked=False)`
- For check tests: patch `notify_item_checked` and `notify_list_complete` (imported from `api.v1.shopping_list.update_item`)
- For unchecked_count (list_complete check): `mock_db.db.query.return_value = MockQuery([])`

### Flutter Test Pattern

`ShoppingListItemTile` tests are pure widget tests (no DI):
```dart
testWidgets('checked item shows strikethrough', (tester) async {
  final item = ShoppingListItem(id: 'i1', name: 'Milk', isChecked: true);
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: ShoppingListItemTile(item: item)),
  ));
  final text = tester.widget<Text>(find.text('Milk'));
  expect(text.style?.decoration, TextDecoration.lineThrough);
});
```

For `_toggleItemChecked` optimistic logic, test the state machine in isolation using a `_CheckOffTester` helper widget (same pattern as `_AddToCartTester` in `add_to_cart_test.dart`).

### Project Structure Notes

- New files:
  - `services/api/tests/test_check_off_items.py`
  - `app/test/features/shopping_cart/check_off_test.dart`
- Modified files:
  - `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` — `_toggleItemChecked` optimistic update

### References

- Epic 8 story 8.3 requirements: `_bmad-output/planning-artifacts/epics.md`
- Backend endpoint: `services/api/src/api/v1/shopping_list/update_item.py`
- Router broadcast: `services/api/src/routers/v1/shopping_list_router.py:145-164`
- Flutter screen: `app/lib/features/shopping_cart/screens/shopping_list_screen.dart:128-140`
- Flutter tile: `app/lib/features/shopping_cart/widgets/shopping_list_item_tile.dart`
- Flutter service: `app/lib/features/shopping_cart/services/shopping_cart_service.dart:89-95`
- ShoppingListItem model (has `copyWith`): `app/lib/features/shopping_cart/models/shopping_list_item.dart:88`
- Existing broadcast tests (pattern reference): `services/api/tests/test_shopping_list_router_broadcasts.py`
- Existing add_to_cart widget tests (pattern reference): `app/test/features/recipes/add_to_cart_test.dart`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- ✅ Task 1: Added optimistic update to `_toggleItemChecked` — applies `copyWith(isChecked: !item.isChecked)` before await, applies server response on success, rolls back on error with snackbar
- ✅ Task 2: Created `test_check_off_items.py` with 12 tests covering check/uncheck success, checked_at/checked_by_user_id fields, 404/403 errors, notify_item_checked, notify_list_complete, and editor access
- ✅ Task 3: Created `check_off_test.dart` with 9 tests covering `ShoppingListItemTile` visual states (strikethrough, checkbox icon), onChecked callback direction, optimistic update flip, rollback on error, and error snackbar
- All 318 backend tests pass, all 214 Flutter tests pass — no regressions

### Senior Developer Review (AI)

**Review Date:** 2026-03-19
**Outcome:** Changes Requested → All Fixed

**Action Items (all resolved):**
- [x] [M1] Race condition in `_toggleItemChecked` — added `_pendingItemIds` set + `finally` block
- [x] [M2] Missing null-guard before optimistic update — added early return if `_list == null`
- [x] [M3] Missing uncheck broadcast test — added `test_uncheck_broadcasts_item_checked_event`
- [x] [L1] `_CheckOffTester` success path had no async delay — added `Completer` parameter; test now verifies true optimistic interim state before server response
- [x] [L2] Misleading comment in `test_check_item_sets_is_checked_true` — clarified comment

### File List

- `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` — `_toggleItemChecked` with optimistic update, race condition guard (`_pendingItemIds`), null-guard
- `services/api/tests/test_check_off_items.py` — 13 backend tests (added uncheck broadcast test)
- `app/test/features/shopping_cart/check_off_test.dart` — 9 Flutter widget tests with proper Completer-based async simulation
