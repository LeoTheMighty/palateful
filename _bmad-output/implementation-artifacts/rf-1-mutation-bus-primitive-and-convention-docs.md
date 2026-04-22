# Story rf-1 — MutationBus primitive + convention docs + test helper

**Epic**: epic-reactive-foundation-home-imports
**Status**: review
**Created**: 2026-04-22

## Scope

Ship the foundational MutationBus primitive the rest of the epic depends on.
Non-autoDispose `Provider<Stream<MutationEvent>>` backed by a module-level
singleton `StreamController.broadcast()`. Sealed `MutationEvent` hierarchy
with every type listed in the events catalog — Recipe*/ImportItem* live,
Meal*/Calendar*/Book*/Pantry*/Profile* as stubs. Plus a top-level
`emitMutation(...)` helper, a Snackbar helper, mutation-failure copy,
convention README, widget-test helper, and unit tests.

## Acceptance criteria (from epic)

1. `mutation_bus.dart` exists with sealed `MutationEvent` + all subtypes
   including stubs for migration epics. ✅
2. `mutationBusProvider` is `Provider<Stream<MutationEvent>>` (non-autoDispose)
   backed by singleton `StreamController.broadcast()`. Multiple subscribers
   each receive every event. ✅
3. Top-level `emitMutation(MutationEvent)` helper — subscribers receive
   before next macrotask. ✅
4. `pumpWithMutation(tester, event)` helper in `app/test/helpers/`. ✅
5. README documents emit/subscribe/add-a-new-type/coarse-key/bulk-event/
   100ms-coalesce recipe/WS-lowering/test-helper-API. ✅
6. Unit test verifies broadcast, no memory leaks, ordering, late-subscribe
   semantics. ✅
7. No event dropped in single-subscriber case (regression guard). ✅

## Files added

- `app/lib/core/state/mutation_bus.dart`
- `app/lib/core/state/mutation_event.dart`
- `app/lib/core/state/mutation_failure_copy.dart`
- `app/lib/core/state/mutation_snackbar.dart`
- `app/lib/core/state/README.md`
- `app/test/helpers/mutation_bus_test_helper.dart`
- `app/test/core/state/mutation_bus_test.dart`

## QA walkthrough

- [ ] `flutter test test/core/state/mutation_bus_test.dart` — all four
      scenarios pass (broadcast, no leaks, ordering, late-subscribe).
- [ ] `dart analyze lib/core/state/` — zero warnings.
- [ ] Visual check README.md renders on GitHub (headings, fenced code).
- [ ] Grep for `StreamProvider.autoDispose<MutationEvent>` — zero hits
      anywhere in the codebase (regression guard against draft's autoDispose
      mistake).
