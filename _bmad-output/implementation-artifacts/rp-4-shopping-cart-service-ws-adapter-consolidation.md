# rp-4 — ShoppingCartService WS adapter consolidation

**Status**: done
**Epic**: epic-reactive-migration-books-profile-pantry-and-polish

## What shipped

Closes AC rp-4 #1–#7. `ShoppingCartService._handleMessage` switch
cases `item_added` / `item_updated` / `item_checked` / `item_removed`
now additionally lower into MutationBus events keyed by
`_currentListId`. Local mutation methods (`addItem`, `updateItem`,
`toggleItemChecked`, `deleteItem`) emit on their success branch.
`presence_update`, `sync_response`, `pong`, `connected`, and malformed
frames do **NOT** emit — they're not mutations.

The external `ShoppingCartService` API (`onItemAdded`, `onItemUpdated`,
`onItemRemoved`, `onPresenceUpdate`, `onSync`, `onWebSocketStateChange`)
is unchanged — every existing consumer keeps working. `ShoppingListScreen`
rewrite onto a dedicated `shoppingListProvider` is **deferred** to a
follow-on polish epic, per resolved question #2.

## Files

### Modified

- `app/lib/features/shopping_cart/services/shopping_cart_service.dart`
  — surgical edits:
  - Import `core/state/mutation_bus.dart`.
  - `addItem`, `updateItem`, `toggleItemChecked`, `deleteItem` each
    add one `emitMutation(...)` call on the success branch before
    returning.
  - `_handleMessage` switch cases add one `emitMutation(...)` each
    after firing the pre-existing StreamController.
  - Added `@visibleForTesting` seams: `handleMessageForTest(data)`
    and `setCurrentListIdForTest(listId)` so the regression test
    can drive the WS path without a real socket.

### New

- `app/test/features/shopping_cart/ws_adapter_emits_mutation_test.dart`
  — 13 tests across two groups:
  - **Local mutation methods emit** (4): add / update / toggle /
    delete each emit the expected event.
  - **WS frames lower to MutationBus** (9): item_added, item_updated,
    item_checked, item_removed each lower; presence_update, pong,
    malformed frame do NOT emit; StreamController sink still fires;
    dual-path (local + WS for same id) emits twice — idempotence
    regression.

## QA walkthrough

### Regression (CI-guarded)

- [x] `ws_adapter_emits_mutation_test.dart` — 13 tests green.
- [x] Existing shopping-cart tests (check_off, item, model) still
  green — external API is source-compatible.

### Manual dogfood (dogfood-proof step 4)

1. Two devices on the same shopping list (Leo + partner).
2. Partner taps + → adds "Milk".
3. Leo's device receives WS `item_added` frame.
   - [ ] Row appears in Leo's list within one frame.
   - [ ] Existing StreamController-based UX unchanged (no regression).

### Deferred (per resolved question #2)

- `ShoppingListScreen` rewrite onto Riverpod `shoppingListProvider`.
  External `ShoppingCartService` API remains source-compatible so
  the rewrite can land as a follow-on polish epic.
