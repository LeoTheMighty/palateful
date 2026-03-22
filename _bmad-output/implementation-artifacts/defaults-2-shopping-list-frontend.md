# Story Defaults.2: Default Shopping List — Frontend UX

Status: complete

## Story

As a user,
I want "Add to Cart" to instantly add items to my default shopping list with a snackbar confirmation,
so that I don't have to pick a list every time I add ingredients from a recipe or calendar.

## Acceptance Criteria

1. "Add to Cart" from recipe detail → items added to default list instantly (no picker) + snackbar "Added to [List Name] · Change"
2. "Add to Cart" from calendar single event → same instant add + snackbar pattern
3. "Generate Weekly Shopping List" from calendar → opens list picker with default pre-selected (bulk = ask once)
4. Tapping "Change" on snackbar → bottom sheet with two options: one-time redirect to different list, OR switch default
5. Cart tab shows a subtle star/pin badge on the default list card
6. Long-pressing any list card on Cart tab shows "Set as default" option
7. If user has only 1 list, no snackbar "Change" option shown (nothing to change to)
8. Creating a new shopping list shows toast "This is now your default list"

## Tasks / Subtasks

- [x] Task 1: Refactor "Add to Cart" on recipe detail (AC: #1, #4, #7)
  - [x] Modify `app/lib/features/recipes/recipe_detail_screen.dart` `_addIngredientsToCart()`
  - [x] If default set → skip picker, add to default, show snackbar
  - [x] If no default but only 1 list → auto-select, show snackbar
  - [x] If no default and 2+ lists → show picker (current behavior), set chosen as default
  - [x] Snackbar: "Added to [Name] · Change" with action callback

- [x] Task 2: Refactor "Add to Cart" on calendar (AC: #2, #3)
  - [x] Modify `app/lib/features/calendar/calendar_screen.dart` `_addIngredientsFromEvent()`
  - [x] Same pattern as Task 1 for single event add
  - [x] `_generateWeeklyShoppingList()` → keep picker but pre-select default

- [x] Task 3: Build "Change" bottom sheet (AC: #4)
  - [x] Create reusable bottom sheet widget (e.g. `DefaultChangeSheet`)
  - [x] Shows all user's shopping lists
  - [x] Two actions per list: "Use this time" (one-time redirect) and "Set as default" (permanent switch)
  - [x] When "Set as default" is tapped → call provider's `setDefaultShoppingList()`

- [x] Task 4: Default badge on Cart tab (AC: #5)
  - [x] Modify cart list card widget to show star/pin icon when `is_default` is true
  - [x] Subtle, non-intrusive — small icon in corner or next to list name

- [x] Task 5: Long-press "Set as default" (AC: #6)
  - [x] Modify `app/lib/features/cart/cart_screen.dart`
  - [x] Add long-press handler on list cards
  - [x] Show bottom sheet/context menu with "Set as default" option
  - [x] Call provider to update default

- [x] Task 6: Auto-set toast on new list creation (AC: #8)
  - [x] After creating a new shopping list, if it was auto-set as default (from Story 1 backend)
  - [x] Show toast: "This is now your default list"

## Dev Notes

- The snackbar pattern: `ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Added to $name'), action: SnackBarAction(label: 'Change', onPressed: _showChangeSheet)))`
- The "Change" bottom sheet is reusable — will be used by recipe book defaults too (Story 3)
- Bulk actions (weekly shopping list) always show picker with default pre-selected — this is the "silent for singles, explicit for bulk" rule
- Depends on Story 1 for the backend + state management

### References

- [Investigation: 05-shopping-list-default-cart.md]
- [Epic: epic-smart-defaults.md]
