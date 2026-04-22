---
description: Review a pull request
---

# /review — Code review checklist

Run an adversarial code review on the current branch. Look for specific issues; don't end with "LGTM" unless every item below is green. Fix findings inline when they're local and reversible (style, typos, small bugs). Escalate anything that would take more than ~5 min or that touches cross-cutting contracts.

Output a review report with 3-10 concrete findings minimum (HIGH / MEDIUM / LOW severity). For each: file_path:line_number, what's wrong, why it matters, and the fix.

## Checklist — reactive mutation wiring (epic-reactive-foundation-home-imports)

These items catch the most common regressions in the MutationBus + service-layer pattern. Go through every one for any PR that touches a recipe, meal, calendar, import, pantry, or profile mutation.

- [ ] **Service-layer emit**: does every new mutation in a `*Service` method call `emitMutation(...)` on the success branch of the API call, BEFORE returning to the caller? (Locked Decision #1.) UI handlers must NOT emit directly — the one exception is `ImportHistoryScreen` (flagged as cleanup debt).
- [ ] **No emit on failure**: is the `emitMutation(...)` call inside the success path only? A mutation that fails must NOT emit — subscribers would refetch against stale state and paper over the error.
- [ ] **Failure snackbar**: does every mutation UI-handler catch-block call `showMutationFailureSnackbar(context, MutationType.X, retry)` instead of `ScaffoldMessenger.showSnackBar(SnackBar(...))`? No ad-hoc snackbars in new code (Design Principle #6).
- [ ] **Bulk events**: for any bulk mutation path, does the service emit exactly ONE bulk event (`RecipeBulkArchived`, etc.), NOT N per-item events? (Locked Decision #3.)
- [ ] **Subscriber wiring**: for a new list surface, does its provider call `ref.read(mutationBusProvider).listen(...)` with `ref.onDispose(sub.cancel)` and invalidate on the relevant event *types*? `ref.listen<Stream<MutationEvent>>(mutationBusProvider, ...)` is a no-op — the stream instance never changes.
- [ ] **No autoDispose on the bus**: is `mutationBusProvider` still `Provider<Stream<MutationEvent>>` (non-autoDispose)? `StreamProvider.autoDispose` would silently drop events in the unmount gap.
- [ ] **Flaky-test guard**: do new reactivity widget tests use `pumpWithMutation(tester, event)` from `app/test/helpers/mutation_bus_test_helper.dart`? No `pumpAndSettle(timeout)` — wall-clock delays flake under CI load.
- [ ] **MutationType + copy**: is every new mutation verb in `MutationType` (enum) + `mutationFailureCopy` (map) in `app/lib/core/state/mutation_failure_copy.dart`? Copy must fit at 320px width — verb + noun, and the Retry button label must not wrap.
- [ ] **Optimistic path parity**: if the UI was optimistic before, it stays optimistic (Locked Decision #6 — reconcile-only for v1). Don't introduce new optimistic paths without a follow-up epic scoped for it.
- [ ] **WS-lowering thinness**: if adding a WS inbound, does the handler just parse → emitMutation? No business logic in the adapter.

## Standard review checklist (general)

- [ ] New test coverage for the happy path + at least one failure mode.
- [ ] No dead code or unused imports.
- [ ] Error messages are user-actionable (not raw stack traces).
- [ ] API contract changes are additive (old clients don't break).
- [ ] Migrations are idempotent + reversible.
- [ ] Secrets are not committed.
- [ ] README / docs updated for user-visible changes.
