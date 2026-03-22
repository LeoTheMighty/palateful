# Story UI.5: Sharing UX Overhaul

Status: complete

## Story

As a user,
I want to share recipes, recipe books, and shopping lists with minimal taps using native iOS sharing,
so that sharing feels quick, natural, and works across any messaging app or social platform.

## Acceptance Criteria

1. Recipe detail screen has a share icon as a primary AppBar action (not in overflow menu)
2. Tapping share on a recipe generates a link AND opens iOS share sheet in one action (1 tap)
3. Recipe book detail screen has a share icon for owners/editors that opens share sheet with invite link (2 taps vs current 5-6)
4. Shopping list share uses deep link + iOS share sheet (replaces manual 6-char code dialog)
5. All `Share.share()` calls include `sharePositionOrigin` for iPad safety
6. Unified `ShareService` handles all sharing consistently
7. Shopping list code-based join remains as a fallback (for manual entry)

## Tasks / Subtasks

- [x] Task 1: Create unified ShareService (AC: #6)
  - [x] Create `app/lib/services/share_service.dart`
  - [x] Methods: `shareRecipe(recipeId)`, `shareRecipeBook(bookId)`, `shareShoppingList(listId)`
  - [x] Each method: generates link via API → opens `Share.share()` with `sharePositionOrigin`
  - [x] Include iPad-safe origin calculation helper
  - [x] Handle error states (API failure, no share target)

- [x] Task 2: Promote recipe sharing to primary action (AC: #1, #2)
  - [x] Modify `app/lib/features/recipes/recipe_detail_screen.dart`
  - [x] Add `IconButton(icon: Icon(Icons.ios_share), onPressed: ...)` to AppBar `actions` before overflow menu
  - [x] Merge `_shareRecipe()` and `_nativeShareRecipe()` into single flow using ShareService
  - [x] Remove `share_link` and `share_native` items from PopupMenuButton
  - [x] Keep "Manage Link" option in overflow for revoking/toggling share links
  - [x] Delete `_ShareLinkSheet` widget (no longer needed)

- [x] Task 3: Add share to recipe book detail (AC: #3)
  - [x] Modify `app/lib/features/recipe_books/recipe_book_detail_screen.dart`
  - [x] Add share `IconButton` to AppBar `actions` (only visible for owners/editors)
  - [x] Extract invite link generation from `RecipeBookMembersScreen._showInviteBottomSheet()`
  - [x] Wire to ShareService.shareRecipeBook()
  - [x] Keep Members screen accessible for managing existing members

- [x] Task 4: Modernize shopping list sharing (AC: #4, #7)
  - [x] Modify `app/lib/features/shopping_cart/screens/shopping_list_screen.dart`
  - [x] Replace `_shareList()` code dialog with ShareService.shareShoppingList()
  - [x] API modification: `services/api/src/api/v1/shopping_list/share_shopping_list.py` — return `deep_link` field alongside share code
  - [x] Keep code-based join screen as fallback for manual entry
  - [x] Add share icon to shopping list AppBar

- [x] Task 5: Fix iPad share sheet anchor (AC: #5)
  - [x] Audit all `Share.share()` and `Share.shareXFiles()` calls
  - [x] Add `sharePositionOrigin` parameter to each:
    ```dart
    final box = context.findRenderObject() as RenderBox?;
    final origin = box != null ? box.localToGlobal(Offset.zero) & box.size : null;
    Share.share(text, sharePositionOrigin: origin);
    ```
  - [x] Files to check:
    - `recipe_detail_screen.dart`
    - `recipe_book_members_screen.dart`
    - `profile_screen.dart`
    - Any new share calls added in this story

- [x] Task 6: QA sharing flows (AC: #1-5)
  - [x] Test recipe share: 1 tap → share sheet opens with link
  - [x] Test recipe book share: 2 taps → share sheet opens with invite link
  - [x] Test shopping list share: share sheet opens with deep link
  - [x] Test on iPad simulator (no crash on share sheet)
  - [x] Test share cancellation (user dismisses sheet)
  - [x] Test share with no network (graceful error)

## Dev Notes

- The `share_plus` package is already a dependency — use `Share.share()` and `Share.shareXFiles()`
- Current deep links use `palateful://` custom scheme — keep for now, universal links (HTTPS) is a separate future story
- The two separate recipe share flows (link-only bottom sheet vs text-only native) should be completely merged into one clean flow
- Shopping list sharing currently uses a 6-char alphanumeric code — the deep link approach is more user-friendly but keep code join as fallback
- Recipe book invite links are already generated server-side — just need to surface them with fewer taps
- This story is independent of Stories 1-4 and can be developed in parallel

### References

- [Investigation: 01-sharing-ux-overhaul.md]
- Current share code: `app/lib/features/recipes/recipe_detail_screen.dart` (_shareRecipe, _nativeShareRecipe, _ShareLinkSheet)
- Current invite code: `app/lib/features/recipe_books/recipe_book_members_screen.dart` (_showInviteBottomSheet)
- Current shopping share: `app/lib/features/shopping_cart/screens/shopping_list_screen.dart` (_shareList)
