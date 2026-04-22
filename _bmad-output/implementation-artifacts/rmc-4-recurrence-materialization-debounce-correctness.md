# rmc-4 — Recurrence materialization debounce correctness

**Status**: done
**Epic**: epic-reactive-migration-meals-calendar

## What shipped

`MealEventCoalescer` extracted into `app/lib/core/state/meal_event_coalescer.dart` as a reusable helper. Replaces the three inline `Timer + debounce` clones from rmc-3's `meal_events_provider.dart`. One canonical implementation → three thinner provider bodies.

Unit test exercises the coalescer entirely inside `FakeAsync.run(...)` — no wall-clock waits. Covers: 52 schedules in 50ms → zero fires before window closes → exactly one fire at window close; cold-stop (cancel mid-window) → zero fires; last-event-elision guard (the 52nd callback is the one that runs — `schedule` replaces the pending callback on each call); re-arm after fire; custom duration; idle-cancel no-op.

Widget stress test (`recurrence_debounce_stress_test.dart`) drives the real `mealEventsByRangeProvider` through the CalendarScreen + ProviderContainer. Emits 52 `MealEventCreated` back-to-back, asserts `MealCalendarService.listMealEvents` is called exactly once after the debounce window closes (no mid-flood refetches). A second scenario asserts that a provider disposed mid-flood cleans up the pending coalescer — no ghost callback fires after the subscription closes.

## Files

- `app/lib/core/state/meal_event_coalescer.dart` — **new**. `MealEventCoalescer` class: `schedule(fn)`, `cancel()`, `isScheduled` (test-only). Defaults to 100ms.
- `app/lib/features/calendar/providers/meal_events_provider.dart` — three `Timer?` inline debounces replaced with `MealEventCoalescer` instances. `ref.onDispose(coalescer.cancel)` replaces the previous `ref.onDispose(() => debounce?.cancel())` pattern. Dead `import 'dart:async'` removed.
- `app/test/core/state/meal_event_coalescer_test.dart` — **new**. 7 unit tests, all inside `FakeAsync.run(...)`.
- `app/test/features/calendar/recurrence_debounce_stress_test.dart` — **new**. 2 widget tests: the 52-event refetch-coalescing assertion, and the dispose-mid-flood cleanup assertion.
- `app/pubspec.yaml` — added `fake_async: ^1.3.1` to `dev_dependencies`.

## Gotchas

- **`FakeAsync.elapse` in a loop**: the fake-async invariant is that timers fire synchronously during `elapse`, so schedule(x)-then-elapse(1ms)-then-schedule(y) is well-defined — schedule(x) sets a timer, elapse(1ms) advances the clock (no fire yet since the timer was set for 100ms), then schedule(y) cancels and replaces.
- **Widget stress test uses `tester.pump`, not `FakeAsync`**: the real provider relies on real Dart timers under the hood, and Riverpod's `ref.invalidateSelf` + refetch lifecycle wants real `await`. `tester.pump(duration)` advances the Flutter clock (which includes the provider's `Timer`) without burning wall time — effectively the same property as `FakeAsync` for this use case, but compatible with the Flutter test binding.
- **Dispose mid-flood** uses a raw `ProviderContainer` + manual `listen().close()` rather than a widget-tree unmount. It's the cleaner way to prove the coalescer's `cancel()` runs via `ref.onDispose`: a widget unmount would also trigger autoDispose but couples the test to route teardown behavior.
- **`Timer(Duration, void Function())` return value**: we don't keep the Timer reference inside the coalescer's schedule body — `_timer = Timer(...)` is the only live reference. When the timer fires, its callback nulls `_timer` before invoking the user callback, so `isScheduled` correctly reports `false` inside the callback.
- **`MealEventCoalescer` does NOT wrap the bus subscription** — only the fire side. The `ref.listen(mutationBusProvider, ...)` wiring stays in the provider body because each provider's filter predicate is different.

## QA walkthrough

### Regression (CI-guarded)

- [x] `meal_event_coalescer_test.dart` — 7 unit tests pass, all under `FakeAsync`.
- [x] `recurrence_debounce_stress_test.dart` — 2 widget tests pass: 52 events → 1 refetch; dispose mid-flood → no ghost fire.
- [x] `calendar_grid_event_reactivity_test.dart` (rmc-3) — still green after the coalescer refactor.
- [x] All 144 calendar + core/state tests pass.

### Manual dogfood (end-to-end — deferred to rmc-5)

- [ ] Create a weekly recurrence rule "Pasta Night" in the plan-meal sheet with end-date 9 weeks out → the 9-event materialization arrives as one refetch (not nine); grid cells populate without flicker or multiple spinners.
- [ ] Navigate away from the calendar tab mid-materialization → no crash, no leaked timers in devtools.
