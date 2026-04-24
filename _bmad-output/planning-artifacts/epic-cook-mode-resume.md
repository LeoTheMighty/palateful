<!-- refined via party-mode 2026-04-22 -->
# Epic: Cook Mode — Persistent Resume (Flutter-only)

## Overview

Cook mode is entirely ephemeral today. If the user backgrounds the app and the OS kills it, or the phone restarts, or the user simply leaves cook mode and comes back — all progress (current step, checked ingredients, active timers, elapsed time) is gone. For a 10-minute single-recipe cook that's mildly annoying; for a 90-minute multi-recipe meal cook (`epic-cook-mode-meal`), it's unacceptable.

This epic introduces a `CookSessionPersister` — a thin service over `SharedPreferences` (mirroring the pattern used by `app/lib/core/services/recipe_cache_service.dart`, which calls `SharedPreferences.getInstance()` directly inside each method; no getIt / DI registration needed) — that persists cook-mode state keyed by a stable identifier. For recipe cook that's `recipe_id`; for meal cook (future) it's `meal_id`. Same service, same schema shape, different keys. On re-entering cook mode for a target with existing state, a Resume / Start Over gate sheet appears first; the user picks one. A new in-cook "Reset" affordance under a header overflow menu lets the user blow away state without having to wait for a kill. Post-cook sheet submission clears the state automatically.

Grounded references (verified at refinement time):
- `_CookModeScreenState` at `cook_mode_screen.dart:37`.
- State fields: `_completedSteps = {}` at `:53`, `_checkedIngredients = {}` at `:54`, `_activeTimers = []` at `:62`, `_cookingStopwatch = Stopwatch()` at `:71`.
- Stopwatch auto-starts in `initState` at `:79` — this matters: Resume must NOT let the stopwatch start fresh at 0 before the gate is resolved. See cmr-2 AC5.
- Methods: `_goToStep` at `:264`, `_nextStep` at `:281`, `_markAllUpToHere` at `:292`, `_toggleIngredient` at `:301`, `_startTimer` at `:312`, `_cancelTimer` at `:368`, `_onTimerComplete` at `:385`, `_startTimerTick` at `:190`.
- `SharedPreferences` pattern: `recipe_cache_service.dart:20, 30, 43, 56, 74, 88, 99, 118` — every method calls `await SharedPreferences.getInstance()` inline; no singleton field, no DI. Mirror exactly.

This epic is Flutter-only. No backend, no schema migration, no infra.

## Goal

Cook-mode progress survives app kill. The user can always Resume exactly where they left off, or explicitly Start Over. The `CookSessionPersister` is a general-purpose service both recipe and meal cook modes use; `epic-cook-mode-meal` gets it for free.

## End-user flow

### Path A — normal cook, no interruption

1. User taps **"Start Cooking"** on a recipe detail screen.
2. No prior state for this recipe → cook-mode screen mounts immediately at step 0 (no gate sheet).
3. User cooks: advances steps, checks ingredients, starts a 10-min timer.
4. Every state change (step advance, ingredient toggle, timer start/stop/cancel/complete) → debounced write (≥ 250ms window) to SharedPreferences under key `cook_session_recipe_<recipeId>`.
5. User finishes cooking, rates via the post-cook sheet, taps Done.
6. On Done → `CookSessionPersister.clear(key)` is called → SharedPreferences key removed.
7. User later taps "Start Cooking" for the same recipe → no prior state → fresh start at step 0.

### Path B — mid-cook kill, Resume

1. User is on step 3 of a 12-step recipe, has a 10-min timer running, 4 ingredients checked, 7 minutes elapsed.
2. OS kills the app (or user force-quits, or phone restarts).
3. User taps "Start Cooking" on the same recipe later.
4. **Resume / Start Over gate sheet** mounts BEFORE the cook UI loads. Content: recipe name, summary line "Picked up from **step 3 of 12** · started **2 h ago** · 4 ingredients checked · 1 timer (done while away)". Two buttons: **Resume** (primary, left) and **Start Over** (secondary destructive, right — per iOS/Android destructive-action-right convention).
5. User taps **Resume**.
6. `CookModeScreen` mounts with state restored: current step = 3, `_completedSteps = {0, 1, 2}`, `_checkedIngredients = {…}`. The `_cookingStopwatch` starts fresh but is **offset** by a persisted `cumulative_elapsed_ms`; effective elapsed = `cumulative_elapsed_ms + stopwatch.elapsedMilliseconds` (a `_restoredElapsedMs` field holds the baseline).
7. The 10-min timer's deadline was in the past (elapsed away-time > 10 min) → it's marked done; a snackbar on mount reads **"While you were away: your 10 min timer finished"** with an OK dismissal.
8. A not-yet-expired timer (e.g., a 60-min roast with 45 min remaining) → restored with the correct remaining duration (`max(0, deadline_ms − now_ms)`); live countdown resumes; OS notification re-scheduled at the original `deadline_ms`.
9. User continues cooking normally.

### Path C — user wants to blow away state mid-cook (no kill needed)

1. User is on step 3, realized they want to restart from scratch (burnt a pan, kid interrupted).
2. User opens the cook-mode **header overflow menu** (new `PopupMenuButton` keyed off `Icons.more_vert`, rightmost in the header after the cooking-time badge — header grows from 4 to 5 icons total) → taps **"Reset cook"**.
3. Confirmation sheet slides up: "Reset this cook session? Your step progress, checked ingredients, and active timers will be cleared." **[Cancel]** left, **[Reset]** right (destructive).
4. User taps Reset → `CookSessionPersister.clear(key)` + in-memory state reset to fresh + all active timers cancelled (including scheduled OS notifications) + snackbar "Cook session reset".
5. User is now at step 0 with no checks, no timers, elapsed time reset to 0. They never left the screen.

### Path D — Start Over at the gate

1. Same setup as Path B — kill mid-cook, re-enter, gate appears.
2. User taps **Start Over**.
3. `CookSessionPersister.clear(key)` → cook-mode screen mounts at step 0, no ingredients checked, no timers, elapsed = 0. Identical to Path A post-clear.

### Path E — stale-state edge (recipe changed since last session)

1. User has a saved session at step 10 for recipe X.
2. Recipe X was edited since — it now has 8 steps, not 12.
3. User taps Start Cooking → Resume gate appears (persister doesn't know about the edit).
4. User taps Resume → the screen's resume flow detects `persisted.current_step >= plan.totalSteps`. Silent fallback: clamp `current_step` to `totalSteps - 1`, keep `_completedSteps` capped to valid indices, show a one-shot snackbar "Recipe changed since your last session — picking up at the last step" so the user understands why their position shifted.
5. Checked-ingredients: recipe's ingredient count might also have changed. Apply the same clamp — drop indices ≥ new count.

## Frontend changes

**New:** `app/lib/features/recipes/cook_mode/services/cook_session_persister.dart`
- Single service over `SharedPreferences`. **No getIt / DI registration.** Each public method calls `await SharedPreferences.getInstance()` inline, exactly like `recipe_cache_service.dart`. Tests use `SharedPreferences.setMockInitialValues({})`.
- Key format: `cook_session_recipe_<uuid>` for recipes; `cook_session_meal_<uuid>` for meals. A helper `CookSessionKey.forRecipe(id)` / `CookSessionKey.forMeal(id)` hides the format.
- Value format (JSON-encoded):
  ```json
  {
    "schema_version": 1,
    "target_kind": "recipe" | "meal",
    "target_id": "<uuid>",
    "started_at_ms": <epoch ms — first-ever mount time>,
    "cumulative_elapsed_ms": <int — sum of all prior cook-stopwatch runs>,
    "current_step": <int>,
    "completed_steps": [<int>, …],
    "checked_ingredients": [<string keys — for recipe cook, the stringified int index; for meal cook, "<componentIdx>:<orderIdx>">, …],
    "active_timers": [
      {
        "label": "<string>",
        "deadline_ms": <epoch ms>,
        "total_duration_s": <int>,
        "source": "extracted" | "regex" | "manual"
      }
    ],
    "updated_at_ms": <epoch ms>
  }
  ```
- API:
  - `Future<CookSessionState?> load(String key)` — returns null if no state. Returns null if `schema_version` is unknown (forward-compat). **On malformed JSON, removes the key and returns null** (prevents stuck-at-gate state). Logs a warning via the existing Flutter error-log client.
  - `Future<void> save(String key, CookSessionState state)` — JSON-encodes, writes. Size-checked: if encoded JSON > 50KB, log a warning and skip the write (defensive against runaway state growth; a real session is ~2KB).
  - `Future<void> clear(String key)` — removes; idempotent (clear on empty key = no-op).
  - `Future<List<String>> listKeys({String prefix})` — enumerate keys matching a prefix.
  - `Future<int> pruneStaleOlderThan(Duration maxAge)` — delete any keys whose `updated_at_ms` is older than `now - maxAge`. Called once on app startup with `maxAge = 30 days`. Returns count pruned.
- `CookSessionState` is a plain Dart class with `fromJson` / `toJson` / `copyWith`. Lives next to the service.

**New:** `app/lib/features/recipes/cook_mode/services/cook_session_debouncer.dart`
- Wraps `CookSessionPersister`. Exposes `markDirty(key, stateProducer)` → schedules a write after 250ms idle. Coalesces multiple `markDirty` calls in the window into a single write.
- On `flushNow()` (awaitable), writes any pending state immediately.
- Consumers call `flushNow()` from `WidgetsBindingObserver.didChangeAppLifecycleState` on `AppLifecycleState.paused` (and from `dispose` as belt-and-suspenders). Pause-lifecycle is the primary flush trigger — `dispose` fires too late when the OS kills the app.

**Modified:** `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `_CookModeScreenState` becomes `WidgetsBindingObserver` (if not already). Override `didChangeAppLifecycleState(AppLifecycleState state)`: on `paused`, call `debouncer.flushNow()`.
- **Critical:** delay `_cookingStopwatch.start()` at `:79` until AFTER the Resume / Start Over gate resolves. Move the `.start()` call into the post-gate hydration path. Otherwise the stopwatch runs during gate display, which corrupts the restored `cumulative_elapsed_ms`.
- On `initState`, before any recipe hydration: call `CookSessionPersister.load(key)`. If non-null, await `showCookResumeGate(context, state)`. On `resume`: populate `_currentStep`, `_completedSteps`, `_checkedIngredients`, `_restoredElapsedMs`, then reconstruct `_activeTimers` (see cmr-5 below), then call `_cookingStopwatch.start()`. On `startOver`: call `CookSessionPersister.clear(key)`, then proceed as fresh; `_cookingStopwatch.start()`.
- Introduce a `_restoredElapsedMs: int` state field (default 0). Every cooking-time UI read becomes `_restoredElapsedMs + _cookingStopwatch.elapsedMilliseconds`. Persisted `cumulative_elapsed_ms` on save = that sum.
- Plumb every state-mutating path through a private `_persistState()` helper that builds a `CookSessionState` snapshot and calls `debouncer.markDirty(key, …)`. Call sites: `_nextStep`, `_goToStep`, `_toggleIngredient`, `_startTimer`, `_cancelTimer`, `_onTimerComplete`, `_markAllUpToHere`, `_restartTimer`.
- Timer-tick handlers (`_startTimerTick` → periodic) do NOT call `_persistState` — timers store absolute `deadline_ms` which doesn't drift on each tick.
- Add a header `PopupMenuButton(icon: Icon(Icons.more_vert))` as the rightmost element in `_buildHeader` (after the cooking-time badge). One menu item: **"Reset cook"** → opens `cook_reset_confirm_sheet.dart`.
- On successful post-cook sheet submission (rating + `cooking_logs` POST succeeds), call `CookSessionPersister.clear(key)` BEFORE `Navigator.pop`. If the POST fails, do NOT clear — user can retry without losing session.
- On `dispose`, call `debouncer.flushNow()` synchronously as belt-and-suspenders (primary flush is `AppLifecycleState.paused`).

**New:** `app/lib/features/recipes/cook_mode/widgets/cook_resume_gate_sheet.dart`
- Bottom sheet. `isDismissible: false`, `enableDrag: false` — explicit button choice required.
- Content: target name (recipe or meal; 20pt weight-600), summary line: "Picked up from **step N of M** · started **<relative>** · K ingredients checked · L timer(s)" (L can include a parenthetical "(done while away)" when one or more timers have expired).
- Button row: **Resume** (primary, left, `FilledButton`), **Start Over** (secondary destructive, right, `TextButton` with `colorScheme.error` foreground).
- Returns `CookResumeChoice.resume` or `CookResumeChoice.startOver` from `showModalBottomSheet<CookResumeChoice>`.
- Uses `CookModeTheme` tokens via the same fallback pattern as `_resolveCookTimer` (falls back to `colorScheme` if the extension isn't registered).

**New:** `app/lib/features/recipes/cook_mode/widgets/cook_reset_confirm_sheet.dart`
- Bottom sheet. Dismissible via outside-tap (= Cancel).
- Content: "Reset this cook session? Step progress, checked ingredients, and active timers will be cleared." (no heading; compact.)
- Button row: **Cancel** (left, `TextButton`), **Reset** (right, `FilledButton` with `colorScheme.error` background — destructive). Destructive action on the right per platform convention.
- Returns `bool` (true = reset confirmed).

**New:** `app/lib/features/recipes/cook_mode/util/relative_time.dart`
- Pure function `String relativeTime(DateTime then, {DateTime? now})`. "just now" < 1 min, "N min ago" < 1h, "N h ago" < 24h, "yesterday" 24–48h, "N days ago" 2–7d, "N weeks ago" >7d. Unit-tested with `now` parameterised.

**App startup:** `app/lib/main.dart` (or whichever bootstrap runs on startup — confirm location) gets one new line: `CookSessionPersister().pruneStaleOlderThan(Duration(days: 30));` (unawaited; best-effort). Runs before the router mounts. 30-day window matches how long "useful" a resumable session can plausibly be.

**Tests:**
- `app/test/cook_session_persister_test.dart` (NEW) — unit tests for the service.
- `app/test/cook_session_debouncer_test.dart` (NEW) — unit tests with `FakeAsync` for the debouncer.
- `app/test/relative_time_test.dart` (NEW) — unit tests for the formatter.
- `app/test/cook_mode_resume_test.dart` (NEW) — full Paths A–E widget tests.
- `app/test/cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart`, `offline_cook_mode_test.dart`: add `setUp(() { SharedPreferences.setMockInitialValues({}); })` at the top of each describe block; add a `tearDown` that clears persister keys so tests don't leak state across each other. Icon-count assertions on the header grow by +1 (the overflow menu).

## Backend changes

None. Rationale: cook-mode state is strictly client-local. No cross-device sync (explicitly out of scope). No new table, no new endpoint. `cooking_logs` — the post-cook rating row — is already persisted via the existing `POST /v1/cooking-logs` path; this epic only clears local state after that succeeds.

## Infrastructure changes

None. Rationale: no new env var, no Terraform, no migration, no CI workflow change. SharedPreferences storage is per-device platform storage, no server-side resource. The 50KB per-session size cap and 30-day prune on startup keep SharedPreferences well below its effective platform budget (~1MB).

## Design principles

- **Absolute deadlines, not remaining durations.** Timer state stores `deadline_ms` (absolute epoch). On Resume, remaining = `max(0, deadline − now)`. Prevents drift across sleep/wake cycles and OS clock changes. (Clock-skew edge case handled in cmr-5 AC8.)
- **Stopwatch uses a restored-baseline pattern.** A `Stopwatch` cannot be "set to elapsed=N"; it always starts at 0. Persist `cumulative_elapsed_ms` = sum of prior runs, plus a new `_restoredElapsedMs` field on the state; display = baseline + live-stopwatch.
- **Flush on pause, not on dispose.** `AppLifecycleState.paused` is the reliable signal that the app may be killed soon. `dispose` fires when the widget unmounts, which is often after the OS has already killed the process. Primary flush is paused; dispose is a fallback.
- **Forward-compatible schema.** `schema_version: 1` is in the value. Old clients reading a newer schema → return null (treat as no state) rather than crash. Never migrate old state to new schema in-place — just let the user re-enter a fresh session. Malformed JSON: clear the key and return null, so the user isn't stuck at a gate that never displays.
- **Debounced writes, not write-per-setState.** Step advance, ingredient toggle, and timer events can fire in bursts; naive synchronous writes would blow out SharedPreferences throughput.
- **Post-cook clear is atomic with log.** State is cleared AFTER the `cooking_logs` write succeeds, not before. Log failure → state stays so the user can retry without losing their session.
- **Gate over auto-resume.** Never silently resume. The user must explicitly choose — UX principle: "the app doesn't decide for you what to do with your half-cooked meal".
- **Destructive action on the right.** Both the gate sheet (Start Over) and the reset-confirm sheet (Reset) put the destructive button on the right, matching iOS/Android convention.
- **Recipe-version-drift: clamp silently.** If the recipe has fewer steps than the saved session records, don't present a confusing error — clamp to the last valid step, show a one-shot snackbar explaining.
- **Cap + prune.** 50KB per-key size cap; 30-day age prune on startup. Prevents SharedPreferences from slowly bloating across a year of half-finished cook sessions.
- **One service, two callers.** `CookSessionPersister` is generic; recipe cook and (future) meal cook use it identically. Don't special-case recipes in the service.
- **Reset is a big-red-button affordance.** Overflow-menu entry, confirmation required, destructive styling, snackbar confirms. Never a single-tap-accident path.

## File structure

Anticipated touched paths:
- `app/lib/features/recipes/cook_mode/services/cook_session_persister.dart` (NEW)
- `app/lib/features/recipes/cook_mode/services/cook_session_debouncer.dart` (NEW)
- `app/lib/features/recipes/cook_mode/util/relative_time.dart` (NEW)
- `app/lib/features/recipes/cook_mode/widgets/cook_resume_gate_sheet.dart` (NEW)
- `app/lib/features/recipes/cook_mode/widgets/cook_reset_confirm_sheet.dart` (NEW)
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart` (MODIFIED — major: gate hook on entry, persist on mutations, overflow menu, post-cook clear, paused-flush lifecycle, `_restoredElapsedMs` field, deferred stopwatch start)
- `app/lib/main.dart` (add `pruneStaleOlderThan(Duration(days: 30))` startup call)
- `app/test/cook_session_persister_test.dart` (NEW)
- `app/test/cook_session_debouncer_test.dart` (NEW)
- `app/test/relative_time_test.dart` (NEW)
- `app/test/cook_mode_resume_test.dart` (NEW)
- `app/test/cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart`, `offline_cook_mode_test.dart` (setUp/tearDown for persister isolation; +1 icon-count for overflow menu)

## Stories

### Story cmr-1 — `CookSessionPersister` service + schema + forward-compat + prune

**AC1** — `cook_session_persister.dart` defines `CookSessionState` class + `CookSessionPersister` class. No DI registration; API surface is `CookSessionPersister().load(key)` / `save(key, state)` / `clear(key)` / `listKeys(prefix: …)` / `pruneStaleOlderThan(Duration)`. Mirrors `recipe_cache_service.dart` style exactly.
**AC2** — `CookSessionState.toJson` / `fromJson` round-trip losslessly. Fields: `schema_version` (always 1 on write), `target_kind`, `target_id`, `started_at_ms`, `cumulative_elapsed_ms`, `current_step`, `completed_steps`, `checked_ingredients` (List<String>), `active_timers` (List of `{label, deadline_ms, total_duration_s, source}`), `updated_at_ms`. Unit-tested for round-trip.
**AC3** — `load(key)`:
  - Returns null when the key is absent.
  - Returns null when `schema_version != 1`.
  - **On JSON parse error: removes the key, logs a warning via the existing error-log client, returns null.** Unit-tested.
**AC4** — `save(key, state)`:
  - JSON-encodes and writes under the key.
  - If the encoded string exceeds **50 KB**, logs a warning and does NOT write (preserves any existing value; user doesn't get stuck). Unit-tested with a synthetic oversized state.
**AC5** — `clear(key)` removes the key; idempotent on an already-empty key (no-op, no throw).
**AC6** — `CookSessionKey.forRecipe(id)` returns `"cook_session_recipe_<id>"`; `forMeal(id)` returns `"cook_session_meal_<id>"`. Helper is the only way callers compute keys.
**AC7** — `listKeys(prefix: "cook_session_recipe_")` returns only recipe keys; prefix filtering works.
**AC8** — `pruneStaleOlderThan(Duration)`:
  - Iterates keys matching the cook-session prefix.
  - For each, loads the JSON value, reads `updated_at_ms`. If `now - updated_at_ms > maxAge`: clear the key.
  - Malformed entries are cleared (treat as stale).
  - Returns the count pruned.
  - Unit-tested with synthetic keys at varying ages.
**AC9** — `cook_session_debouncer.dart` exposes `CookSessionDebouncer(persister)` with `markDirty(key, CookSessionState Function())` + `flushNow()`.
  - `markDirty` schedules a 250ms idle timer; subsequent calls within the window reset the timer. When it fires, invoke the latest `stateProducer` and call `persister.save(key, state)`.
  - `flushNow()` cancels the pending timer, invokes the latest `stateProducer`, awaits the save, returns. Idempotent if nothing pending.
  - FakeAsync-driven unit test: markDirty × 5 within 100ms → exactly 1 save call after 250ms elapses.
  - FakeAsync-driven unit test: markDirty then flushNow within 100ms → exactly 1 save call, no additional save after the 250ms window.
**AC10** — `app/lib/main.dart` (or bootstrap location) invokes `CookSessionPersister().pruneStaleOlderThan(Duration(days: 30));` once before the router mounts. Unawaited (best-effort; must not block startup). Add a short code comment: `// Prune cook sessions older than 30 days on startup (epic-cook-mode-resume).`
**AC11** — `npx nx run app:test` green; no new lint errors; `npx nx run app:analyze` clean.

### Story cmr-2 — Wire recipe cook mode writes (debounced) + lifecycle flush

**AC1** — `_CookModeScreenState` mixes in `WidgetsBindingObserver`. `initState` calls `WidgetsBinding.instance.addObserver(this)`; `dispose` calls `removeObserver`.
**AC2** — `didChangeAppLifecycleState(AppLifecycleState state)` override: when `state == AppLifecycleState.paused`, calls `await debouncer.flushNow()`. Ensures pending writes survive OS kill.
**AC3** — A `CookSessionDebouncer` is constructed in `initState` and assigned to a field. On `dispose`, call `await debouncer.flushNow()` (belt-and-suspenders fallback to AC2).
**AC4** — A private helper `_persistState()` builds a `CookSessionState` snapshot from current in-memory state (including `cumulative_elapsed_ms = _restoredElapsedMs + _cookingStopwatch.elapsedMilliseconds`, `started_at_ms` carried from initial save or stamped first-time) and calls `debouncer.markDirty(key, …)`.
**AC5** — `_cookingStopwatch.start()` at `:79` is moved out of `initState`'s immediate path. New order: `addObserver`, construct debouncer, load persisted state → gate if non-null → then call `_cookingStopwatch.start()` after the Resume / Start Over decision. This matters: stopwatch must not run while the gate is displayed or while the recipe is loading, otherwise `cumulative_elapsed_ms` drifts.
**AC6** — State-mutating handlers call `_persistState()` at the end: `_nextStep`, `_previousStep`, `_goToStep`, `_toggleIngredient`, `_startTimer`, `_cancelTimer`, `_onTimerComplete`, `_markAllUpToHere`, `_restartTimer`.
**AC7** — Timer-tick handlers (the periodic callback in `_startTimerTick` at `:190`) do NOT call `_persistState` — absolute `deadline_ms` doesn't drift on tick.
**AC8** — Widget test: pump `CookModeScreen(recipeId: "r1")`, simulate recipe load complete (no gate — no prior state), advance to step 3, check ingredient 0, start a 10-min timer. Push the app to `AppLifecycleState.paused`. Assert SharedPreferences now contains JSON under `cook_session_recipe_r1` with `current_step == 3`, `checked_ingredients` containing "0", `active_timers` non-empty with a `deadline_ms` ≈ now + 10 min.
**AC9** — Widget test: advance rapidly (5 step advances within 100ms via `tester.pump(Duration(milliseconds: 20))` × 5). Assert — using `FakeAsync` to elapse the 250ms window — exactly one save call occurs (coalescing works).
**AC10** — Widget test: pump, mutate, then simulate `AppLifecycleState.paused` without elapsing the debounce window. Assert flushNow triggered exactly one save.
**AC11** — `cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart` get `setUp(() { SharedPreferences.setMockInitialValues({}); })` + `tearDown(() async { await CookSessionPersister().clear(key); })` scaffolding. Icon-count assertions in the header grow by +1 (the overflow menu).

### Story cmr-3 — Resume / Start Over gate sheet on entry

**AC1** — `cook_resume_gate_sheet.dart` exists and exports `CookResumeChoice` enum (`resume`, `startOver`) + `showCookResumeGate(BuildContext, CookSessionState)` helper.
**AC2** — Gate renders: target name (recipe name from the loaded state's associated recipe — fetched by the screen before gating; fallback: target id UUID if fetch failed), summary line "Picked up from **step N of M** · started **<relative>** · K ingredients checked · L timer(s)" (M is `state.current_step+1` if the screen doesn't yet know `totalSteps`; show "step N" without `/M` in that case).
  - When any timer has expired (deadline_ms < now): append " (done while away)" to the timer count.
  - Example: "Picked up from step 3 of 12 · started 2 h ago · 4 ingredients checked · 1 timer (done while away)".
**AC3** — Button row: **Resume** on the left (primary `FilledButton`), **Start Over** on the right (secondary `TextButton` with `colorScheme.error` foreground). Destructive-right convention.
**AC4** — Sheet is **non-dismissible**: `isDismissible: false`, `enableDrag: false`. Explicit choice required. Back-button press: no-op (consumed by a `PopScope`).
**AC5** — `relative_time.dart` defines `String relativeTime(DateTime then, {DateTime? now})`. "just now" < 1 min, "N min ago" < 1h (singular "1 min ago" for exactly 1), "N h ago" < 24h, "yesterday" 24–48h, "N days ago" 2–7d (including fractional rounding), "N weeks ago" >7d. Unit-tested at each boundary with `now` parameterised.
**AC6** — `cook_mode_screen.dart` on `initState`, before recipe hydration, calls `CookSessionPersister().load(key)`. If non-null: hydrate the recipe (so the gate knows the recipe name + total step count), then await `showCookResumeGate`. On `resume`: populate in-memory state from the saved `CookSessionState`; set `_restoredElapsedMs = state.cumulative_elapsed_ms`; clamp `_currentStep` to `[0, totalSteps-1]` (Path E drift guard); start stopwatch; reconstruct timers (cmr-5). On `startOver`: call `CookSessionPersister.clear(key)`; proceed as fresh; start stopwatch.
**AC7** — Widget test `cook_mode_resume_test.dart`: seed SharedPreferences with saved state for recipe X at step 3 with 4 checked ingredients + cumulative_elapsed_ms = 420000 (7 min). Pump `CookModeScreen(recipeId: X)`. Assert the gate sheet is visible. Tap Resume. Assert cook mode mounts at step 3 with 4 ingredients pre-checked; assert cooking-time UI reads ≥ 7 min (accounting for mount delay).
**AC8** — Widget test: same seed. Pump. Tap Start Over. Assert cook mode mounts at step 0; no checks; SharedPreferences key cleared; cooking-time UI reads 0.
**AC9** — Widget test: no seed → no gate sheet → direct mount at step 0. Regression guard.
**AC10** — Widget test (Path E drift): seed state with `current_step = 15`, but the recipe has only 8 steps. Tap Resume. Assert cook mode mounts at step 7 (totalSteps-1), snackbar "Recipe changed since your last session — picking up at the last step" is visible, `_completedSteps` is clamped to indices < 8.
**AC11** — Widget test (malformed state): seed SharedPreferences with a raw string that isn't valid JSON under the key. Pump. Assert: no gate sheet, no crash, screen mounts at step 0, SharedPreferences key is now empty (cleared on load failure per cmr-1 AC3).
**AC12** — Widget test (back-button on gate): pump, gate appears, press hardware back button via `tester.pageBack()` (or simulate the equivalent). Assert: gate remains, no dismiss, state untouched.
**AC13** — Gate sheet uses `CookModeTheme` tokens via fallback; renders correctly under both light and dark.

### Story cmr-4 — In-cook Reset affordance + auto-clear on Done

**AC1** — `cook_mode_screen.dart` `_buildHeader` gains a `PopupMenuButton(icon: Icon(Icons.more_vert))` as the rightmost header element (after the cooking-time badge). Menu has one item: **"Reset cook"**. Icon-count assertions across tests adjust accordingly.
**AC2** — Tapping Reset opens `cook_reset_confirm_sheet.dart` (new). Confirm sheet body: "Reset this cook session? Step progress, checked ingredients, and active timers will be cleared." Buttons: **Cancel** left (`TextButton`, no destructive styling), **Reset** right (`FilledButton` with `colorScheme.error` background — destructive; the right side is reserved for the destructive action per platform convention).
**AC3** — On Reset confirm:
  1. `CookSessionPersister().clear(key)`.
  2. Cancel all active timers (dispose `Timer.periodic`, cancel OS notifications via `cook_timer_notification_service`).
  3. Reset in-memory state: `_currentStep = 0`, `_completedSteps.clear()`, `_checkedIngredients.clear()`, `_activeTimers.clear()`, `_cookingStopwatch.stop(); _cookingStopwatch.reset(); _cookingStopwatch.start();` (fresh run), `_restoredElapsedMs = 0`.
  4. Snackbar: "Cook session reset" (2 s duration).
  5. No navigation — user remains on cook mode at step 0.
**AC4** — Post-cook sheet submission flow: after `cooking_logs` write succeeds, call `CookSessionPersister().clear(key)` BEFORE `Navigator.pop`. If the `cooking_logs` write fails (offline / 500), state is NOT cleared (covered by AC7).
**AC5** — Widget test: advance to step 3, check 2 ingredients, start a 5-min timer. Open overflow → Reset → confirm. Assert: in-memory state reset, SharedPreferences key gone, timer cancelled (no periodic ticks), snackbar visible. User stays on cook mode at step 0.
**AC6** — Widget test: complete cook, rate, tap Done. Mock `cooking_logs` POST succeeds. Assert: SharedPreferences key cleared after success, screen popped.
**AC7** — Widget test: complete cook, submit rating, mock `cooking_logs` POST to fail. Assert: SharedPreferences key is NOT cleared; user can retry.
**AC8** — Widget test: tap Reset → Cancel (or outside-tap on the sheet). Assert no state changes, no clear, no snackbar.
**AC9** — Widget test: tap Reset → confirm → assert the new `_cookingStopwatch` restart is clean (cooking-time UI reads ~0 immediately after, grows from there).

### Story cmr-5 — Timer rebuild on Resume + "while you were away" snackbar

**AC1** — On Resume (cmr-3 AC6), the saved `CookSessionState.active_timers` is reconstructed into `_activeTimers`. For each saved entry:
  - Let `remaining_s = (deadline_ms - now_ms) / 1000`.
  - If `remaining_s > 0`: create an `_ActiveTimer` with the correct remaining duration, schedule its periodic tick, **re-schedule** the OS notification at `deadline_ms` via `cook_timer_notification_service.schedule(...)` (the old notification may or may not have survived the kill; re-scheduling is idempotent from the OS's perspective if the payload matches).
  - If `remaining_s <= 0`: do NOT add to `_activeTimers`; track in a local `_expiredWhileAway: List<String>` list (labels).
**AC2** — After mount, if `_expiredWhileAway` is non-empty, show a consolidated snackbar:
  - **If `_expiredWhileAway.length ≤ 3`**: list labels. Example: "While you were away: **simmer, roast** timers finished" (comma-joined; with "and" before the last for readability: "simmer, roast, **and** bake").
  - **If `_expiredWhileAway.length ≥ 4`**: consolidated count. Example: "While you were away: **5 timers** finished".
  - Duration: 5 s (longer than default since the info is meaningful).
  - OK dismissal (snackbar action).
**AC3** — Live Activity service (iOS) is NOT restarted on Resume — live activities are OS-ephemeral and get cleaned up by the OS when the app dies. Resume leaves them off; a new timer started post-Resume starts a fresh live activity. Add a code comment documenting this.
**AC4** — OS notification re-scheduling: on Resume, for each non-expired restored timer, call `cook_timer_notification_service.schedule(...)` with the saved `deadline_ms`. Does not require cancelling a phantom notification first — idempotency on the notification id (the timer's label + deadline hash) is assumed; if not present in the service, note it and add a `cancelAllCookTimerNotifications()` call before re-scheduling.
**AC5** — Widget test: seed state with `active_timers: [{label: "simmer", deadline_ms: <5min from now>, total_duration_s: 600, source: "extracted"}]`. Pump → Resume. Assert active-timers row shows "simmer 5:00" (approx, ±1s for mount delay). Assert `cook_timer_notification_service` mock received a `schedule` call for the right deadline.
**AC6** — Widget test: seed state with `active_timers: [{label: "roast", deadline_ms: <10 min AGO>, total_duration_s: 1800, source: "manual"}]`. Pump → Resume. Assert active-timers row is empty. Assert snackbar "While you were away: **roast** timer finished" is visible (singular form for length 1).
**AC7** — Widget test: seed state with two expired + one still-running timer. Pump → Resume. Assert active-timers row shows the one running timer. Snackbar "While you were away: <label1>, <label2> timers finished" (both labels listed, length 2).
**AC8** — Widget test: seed state with four expired timers. Pump → Resume. Assert snackbar "While you were away: **4 timers** finished" (consolidated count, not listed).
**AC9** — Widget test (clock-skew backward): seed state with `started_at_ms` in the FUTURE (simulating the device clock moved backward since save). Assert: no negative-duration timer, no crash; treat any timer whose `deadline_ms < now` as expired and fire snackbar; timers whose `deadline_ms > now` restore with computed remaining (which might be larger than `total_duration_s` in this skew case — that's acceptable; snackbar mentions "recheck your timers" if skew detected? Out of scope — just don't crash, deterministic fallback).
**AC10** — Widget test (clock-skew forward): seed state with `deadline_ms` very far in the past (> 24 h ago). Assert timer marked expired via the standard path; no special copy.

## Dependencies

- **Internal:** cmr-1 blocks cmr-2 through cmr-5 (everything needs the service). cmr-2 → cmr-3 sequence is load-bearing (persistence must write before gate can read). cmr-3 and cmr-4 both edit `cook_mode_screen.dart` `_buildHeader` / `initState` — serialize merges for cleanliness. cmr-5 depends on cmr-3's Resume-flow hook.
- **Cross-epic:**
  - `epic-cook-mode-remove-chat` (planned): ideally ships first so cmr-4's `_buildHeader` modification (adding the overflow menu) doesn't reconcile around the chat button. If chat ships second, the overflow's header slot is the same; merge is straightforward.
  - `epic-cook-mode-polish` (backlog): cmp-2 also edits `_buildHeader`. Whoever ships second reconciles. Tokens from `CookModeTheme` (cmp-1) are picked up by the new gate + confirm sheets via fallback helpers.
  - `epic-cook-mode-meal` (planned): **hard downstream dep** — consumes `CookSessionPersister` and debouncer directly. This epic must ship first.

## Open questions for the user

- **Stale-prune window.** Draft picks 30 days. Too aggressive? Too lax? (A session you started a month ago and ghosted isn't useful anymore, but the number is arbitrary. Flag if this should be 14 or 90 days.) — Default 30; no change unless user objects.
- **Clock-skew backward snackbar copy.** The design keeps it silent — timer just displays with the restored remaining, even if that looks wrong (e.g., "4h remaining" on a 10-min timer because the clock rolled back). Alternative: a one-shot snackbar "Your device clock changed since this cook started — re-check your timers." Only relevant for the rare traveler-crossing-timezones case. — Default silent; note here.
- **50 KB size cap.** Arbitrary and defensive. A real session is ~2 KB. If someone hits the cap, state won't save silently — the user won't notice until they re-enter. Flag if this should be an error dialog instead of a silent skip. — Default silent-skip-plus-warning-log.
