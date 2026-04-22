# `core/state/` — MutationBus reactivity primitives

The primitives in this directory make local mutations and WS frames reach
every UI surface that displays the mutated data, without a manual pull-to-
refresh.

## Files

- `mutation_event.dart` — sealed `MutationEvent` hierarchy, one case per
  mutation type, plus stubs for the two migration epics.
- `mutation_bus.dart` — singleton `StreamController.broadcast()`, the
  `mutationBusProvider` Riverpod wrapper, and the `emitMutation(...)`
  helper for non-Riverpod callers (services, WS adapters).
- `mutation_failure_copy.dart` — `MutationType` enum → `(verb, noun)` copy.
- `mutation_snackbar.dart` — `showMutationFailureSnackbar(...)` — the
  single entry point for mutation-failure toasts.

## Emit — service-layer rule (Locked Decision #1)

Every mutation emit site MUST be inside a `*Service` method, on the
success branch of the API call, **before** returning to the caller. UI
handlers await the service call; they do not emit.

```dart
class RecipeService {
  Future<Map<String, dynamic>> createRecipe(String bookId, Map<String, dynamic> data) async {
    final response = await _apiClient.createRecipe(bookId, data);
    final recipe = Map<String, dynamic>.from(response.data as Map);
    emitMutation(RecipeCreated(
      recipeId: recipe['id'].toString(),
      recipe: recipe,
      bookId: bookId,
    ));
    return recipe;
  }
}
```

One epic-scoped exception: `ImportHistoryScreen` emits directly from the
widget because there is no `ImportItemService` today. This is flagged as
cleanup debt in the epic's Risks section — don't replicate the pattern.

## Subscribe — which `ref.*` call to use (Locked Decision #2)

| Intent                                       | API                                  | Where                                                      |
| -------------------------------------------- | ------------------------------------ | ---------------------------------------------------------- |
| Bus event fires → refetch my data            | `ref.invalidateSelf()`               | Inside `ref.listen(mutationBusProvider, ...)` in a provider |
| Bus event fires → refetch a sibling provider | `ref.invalidate(siblingProvider)`    | From a listener that owns the sibling's scope              |
| User pulls-to-refresh                        | `ref.refresh(provider)`              | From the UI handler only                                   |
| Family-member refetch                        | `ref.invalidate(recipeProvider(id))` | Inside `ref.listen` after filtering `event.recipeId == id` |

Canonical shape for a list provider that reacts to a bus event type:

```dart
final homeContentProvider =
    FutureProvider.autoDispose<HomeContent>((ref) async {
  ref.keepAlive();

  // `ref.listen` on a `Provider<Stream<T>>` only fires on *value
  // change*; the bus's stream instance is stable for the app lifetime,
  // so read-once + listen + cancel-on-dispose is the correct shape.
  final sub = ref.read(mutationBusProvider).listen((event) {
    if (_shouldInvalidate(event)) ref.invalidateSelf();
  });
  ref.onDispose(sub.cancel);

  return _loadHomeContent();
});

bool _shouldInvalidate(MutationEvent event) => switch (event) {
  RecipeCreated() ||
  RecipeUpdated() ||
  RecipeArchived() ||
  RecipeUnarchived() ||
  RecipeFavorited() ||
  RecipeForked() ||
  RecipeMoved() ||
  RecipeBulkArchived() ||
  MealCreated() ||
  MealUpdated() ||
  MealArchived() ||
  MealFavorited() => true,
  _ => false,
};
```

> **Why `ref.read` + `.listen`, not `ref.listen<Stream>(...)`.** Riverpod's
> `ref.listen` on a `Provider<T>` fires only when the provider's *value*
> changes. Since the bus wraps a module-level singleton
> `StreamController.broadcast()`, the `Stream<MutationEvent>` instance
> never changes — so `ref.listen(mutationBusProvider, ...)` would never
> fire its inner `stream.listen` subscription. `ref.read(...)` +
> `stream.listen(...)` + `ref.onDispose(sub.cancel)` is the shape that
> actually subscribes.

## Coarse-key rule (Design Principle #1)

One event invalidates **one list provider**, not twenty item providers.
Subscribers opt in by event *type*, not by identity. If a list provider
doesn't care about RecipeFavorited, it just doesn't list the type in its
filter.

## Bulk-event rule (Locked Decision #3)

Bulk mutations emit a first-class bulk event and **suppress per-item
events**. `RecipeService.bulkArchiveRecipes([id1, id2, ...])` emits exactly
one `RecipeBulkArchived(recipeIds: [...], bookId)` — not N `RecipeArchived`.
Subscribers that care handle both singular and bulk types.

## 100ms coalesce fallback (Locked Decision #4)

For non-bulk event *floods* (e.g. a partner typing notes across many
recipes in < 1s, lowered into the bus via the WS adapter), subscribers MAY
coalesce with a 100ms debounce in their `ref.listen` body. Shape:

```dart
Timer? debounce;
ref.listen<Stream<MutationEvent>>(mutationBusProvider, (_, stream) {
  stream.listen((event) {
    if (!_shouldInvalidate(event)) return;
    debounce?.cancel();
    debounce = Timer(const Duration(milliseconds: 100), () {
      ref.invalidateSelf();
    });
  });
});
ref.onDispose(() => debounce?.cancel());
```

This is a **subscriber-side** fallback, not a bus-side debounce. First-
class bulk events are simpler and deterministic; reach for coalescing
only when you know an event type arrives in bursts.

## WS-lowering rule

The existing WebSocket inbound handler (shopping list, recipe-book recipe
CRUD) translates WS frames into `emitMutation(...)` calls via a thin
adapter. Downstream subscribers cannot distinguish "my mutation" from
"partner's WS frame" — which is the point. Keep new WS handlers equally
thin; they should never do business logic beyond "parse frame → emit".

Idempotency note: a local mutation emits an event AND the backend also
broadcasts a WS frame that the adapter lowers into the same event type.
Subscribers see two invalidations; two refetches are wasteful but not
incorrect. If profiling shows a hot path, dedupe window goes in the WS
adapter (not scope for rf-\*).

## Adding a new event type

1. Add a case to `MutationEvent` in `mutation_event.dart`, including
   category, payload fields, and const constructor.
2. If any exhaustive `switch` over `MutationEvent` exists (provider
   filters, subscriber classifiers), add a branch — the Dart analyzer
   flags missing branches at compile time for sealed types.
3. Add an entry to `MutationType` + `mutationFailureCopy` if the new
   event has a UI-driven failure path.
4. Service method emits the event on the success branch. UI handler's
   catch calls `showMutationFailureSnackbar(context, type, retry)`.
5. One regression widget test: render the surface, emit the new event,
   pump one microtask + one frame, assert the new state is visible
   without pull-to-refresh.

## Test helper — `pumpWithMutation`

`app/test/helpers/mutation_bus_test_helper.dart` exposes
`pumpWithMutation(tester, event)` — emits the event, pumps one microtask,
pumps one frame. Every reactivity widget test uses this helper; never
`pumpAndSettle(timeout)`.

```dart
await pumpWithMutation(
  tester,
  RecipeCreated(recipeId: 'r-99', recipe: {...}, bookId: 'b-1'),
);
expect(find.text('New Recipe'), findsOneWidget);
```

## Code-review checklist

(mirrored into `.claude/commands/review.md` via rf-6)

- [ ] Does every new mutation in a `*Service` method call
      `emitMutation(...)` on the success branch?
- [ ] Does every mutation UI-handler catch-block call
      `showMutationFailureSnackbar(...)` instead of
      `ScaffoldMessenger.showSnackBar(...)`?
- [ ] For a bulk mutation path, is exactly one bulk event emitted (not N
      per-item events)?
- [ ] For a new list surface, does its provider `ref.listen` on the bus
      and `invalidateSelf()` on the relevant event types?
