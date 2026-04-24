<!-- refined via party-mode 2026-04-20 -->
# Epic: Cook Mode Timers — Extraction + Manual Escape Hatch (Full-stack)

## Overview

Cook Mode has a client-side regex that detects "25 minutes" in a step's instruction and offers a "Set 25 min timer" button. It matches the first occurrence, doesn't handle ranges, decimals, or aliases, and gives the user no fallback when it doesn't fire. Meanwhile, the `recipe_step.timers` JSONB column (in prod since 2026-01-29, commit `4f52574`) is fully wired through the DB, the `StepResponse` schema, and the recipe GET endpoint — but **no extractor populates it**. The AI extractor today dumps all steps into a single `instructions` string (`ai_extractor.py:298`); `create_recipe_task` has a structured-steps path at `:134` that nothing feeds into from the AI route.

This epic wires the whole feature end-to-end: the AI extractor starts emitting structured `steps: [{order, instruction, timers}]`, `create_recipe_task`'s existing `steps` path persists them, eval fixtures measure quality, the frontend prefers the structured field, the frontend regex is upgraded for the fallback case, and a **manual timer entry button is always visible in the header** so the user is never stuck without a timer.

## Goal

When a user imports a recipe, the in-cook experience shows one "Set N-min timer" button per actually-tended duration in the step. When the extractor misses (legacy recipes, edge phrasing), the upgraded regex finds it. When both miss, a timer icon in the cook-mode header lets the user enter one manually. In all three paths, the started timer behaves identically — same notifications, same detail sheet, same completion haptic.

## End-user flow

### Path A — recipe imported under the new pipeline

1. User imports a URL → AI extractor emits `steps: [{order:1, instruction:"Simmer for 3-5 minutes, stirring occasionally", timers:[{duration_minutes:3, label:"simmer"}]}, …]` → `create_recipe_task` writes `RecipeStep(... timers=[...])` → GET returns `step.timers` populated.
2. User opens the recipe, taps **"Cook"**, lands on step 2.
3. Below the instruction card, an `OutlinedButton.icon` reads **"3 min simmer"** (concise label). Long-press or hover shows `Tooltip` "3–5 min in recipe" so the range isn't lost.
4. User taps the button → 3-min countdown appears in the active-timers row → OS notification scheduled → user backgrounds the app.
5. Three minutes later, notification fires; user returns to cook mode → snackbar says **"Timer done: simmer"**.

### Path B — legacy recipe (no extracted timers)

1. User opens a recipe imported before this epic. Step 2 reads "Bake 25 minutes, rotate at 12, broil last 2 minutes."
2. Because `step.timers` is empty/null, the frontend regex fires. It finds **three** durations: 25 min, 12 min, 2 min.
3. Three inline `OutlinedButton.icon`s render in a horizontally-scrollable row (no fixed count cap; the row scrolls if needed — matches the active-timers row pattern at `cook_mode_screen.dart:666`).
4. User taps "25 min" → same flow as Path A.

### Path C — neither path fires, user wants a timer

1. User opens a recipe. Step 4 reads "Let the dough rise until doubled" (no extracted timer, no regex match).
2. No inline buttons show — and that's fine, because the **header timer icon is always there**.
3. User taps the `Icons.timer_outlined` button in the cook-mode header (48×48 tap target, fits alongside the existing 5 header elements without crushing the recipe title).
4. A bottom sheet opens: a numeric text field for minutes (1–360, with `min` suffix adornment), optional short label (default "Timer", max 40 chars), "Start" `FilledButton`.
5. User enters `45`, label "rise", taps Start → timer shows in the active-timers row identically to paths A and B.
6. User opens the sheet again, accepts the default label "Timer" → the new timer lands as "Timer 2" (auto-numbered when an existing active timer has the same label) so both chips are disambiguable.

## Frontend changes

**Modified:** `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `_populateFromData` (`:204–217`) — `_steps` becomes `List<_StepData>` with `{instruction: String, timers: List<StepTimer>}`. Parses `step['timers']` defensively:
  - `null` or missing key → `[]`.
  - Non-list value → `[]`.
  - Per-entry: `{"duration_minutes": int 1..360, "label": string ≤40}` — malformed entries (wrong type, out-of-range, missing fields) silently skipped.
- `_buildStepContent` replaces the single-regex path at `:737–856` with a source-ordered resolution:
  1. If `_steps[_currentStep].timers` is non-empty, build one `OutlinedButton.icon` per entry (duration + label).
  2. Else, run the upgraded regex over `instruction`; build one button per match.
  3. Always render inside a horizontally-scrollable `SingleChildScrollView` row — no fixed cap, no "+N more" sheet (drops the 4-button cap from the draft; scroll is the overflow pattern).
  4. **Hybrid is fallback, not merge:** when `step.timers` is present and non-empty, the regex is NOT consulted — even if `timers` has 1 entry and the instruction mentions 3 durations.
- `_buildHeader` — new `IconButton(Icons.timer_outlined, tooltip: "Add a timer")` between the AI-chat button and the cooking-time pill. **48×48 tap target** (not 64×64) to fit the 360dp header. Visible in online and offline modes; visible regardless of step's extracted/regex timers. Tap → `_showManualTimerSheet()`.
- `_showManualTimerSheet()` opens the new `ManualTimerSheet`. On Start, constructs label via `_disambiguateTimerLabel(userLabel)` — if any active timer already has that exact label, append " 2", " 3", etc. Calls `_startTimer(Duration(minutes: n), finalLabel)` — no new path; reuses existing implementation.

**New:** `app/lib/features/recipes/cook_mode/widgets/manual_timer_sheet.dart` — bottom sheet. Numeric text field with `TextInputType.number`, `inputFormatters: [FilteringTextInputFormatter.digitsOnly]` (blocks paste of non-digits on iOS), `suffixText: "min"` adornment. Validates `1 ≤ minutes ≤ 360`; Start button disabled otherwise. Label field `maxLength: 40`, default "Timer", `textInputAction: TextInputAction.done`. Returns `(minutes, label)` on Start. Uses `_resolveCookTimer(context)` for accents.

**New:** `app/lib/features/recipes/cook_mode/widgets/step_timers_row.dart` — takes `List<StepTimer>` (from either source), renders each as an `OutlinedButton.icon` inside a horizontally-scrollable `SingleChildScrollView`. Uses `_resolveCookTimer(context)` for token resolution.

**New:** `app/lib/features/recipes/cook_mode/util/timer_regex.dart` — pure-Dart helper. `List<StepTimer> extractTimers(String instruction)`:
- Caps input at 2000 chars (prevents catastrophic backtracking on adversarial inputs).
- Multi-match via `allMatches` (up to 10 matches returned).
- Ranges: `(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)` (case-insensitive). Takes **lower bound** as the timer duration; stores the upper bound in the `StepTimer.rangeUpperLabel` field (consumed by the button's tooltip, not the label itself).
- Decimals: `0.5 hour` → 30 min; `1.5 hr` → 90 min.
- Alias map: `h/hr/hrs/hour/hours` → hours, `m/min/mins/minute/minutes` → minutes, `s/sec/secs/second/seconds` → seconds.
- Returns empty list (not null) when nothing matches.

**New:** `app/lib/features/recipes/cook_mode/util/cook_timer_token.dart` — single `Color _resolveCookTimer(BuildContext)` helper. Returns `context.cookModeTheme.cookTimer` when the `CookModeTheme` extension is registered; `Theme.of(context).colorScheme.tertiary` otherwise. Both `manual_timer_sheet.dart` and `step_timers_row.dart` call this helper; no duplicate fallback logic.

**Model:** `StepTimer` class — `{durationMinutes: int, label: String, rangeUpperLabel: String?}`. Lives next to `timer_regex.dart` (feature-local; no new `models/` layer). `fromJson(Map<String, dynamic>)` + defensive parsing. Deliberately no app-wide model layer — `cook_mode_screen` keeps its `Map<String, dynamic>` recipe for v1 and pulls timers into `_StepData` at `_populateFromData` time.

## Backend changes

**Modified:** `libraries/utils/utils/schemas/recipe_extraction_schema.py`
- Top-level schema gains `steps: array<{order: int, instruction: string, timers: array<{duration_minutes: int, label: string}>}>` alongside the existing `instructions: string` field. `instructions` remains for backward compatibility when the model emits it; `steps` is the preferred path going forward.
- Manual validator extended — `timers` must be array; each entry is a dict; per-entry validation is **permissive**: invalid entries get filtered in `create_recipe_task`, not the schema layer (so borderline model output doesn't fail the import).

**Modified:** `libraries/utils/utils/services/recipe_extractors/ai_extractor.py`
- Prompt is extended with:
  - `steps` array schema fragment identical to the JSONSchema.
  - Explicit instruction: "For each step, populate `timers` with **actively-tended** durations (simmer N min, bake N min, fry N min). Do NOT include passive waits (rest overnight, marinate 4+ hours, cool completely) — those are not timers."
  - One positive example: *"Simmer for 10 minutes, stirring."* → `timers: [{duration_minutes: 10, label: "simmer"}]`.
  - One negative example: *"Let dough rise overnight."* → `timers: []`.
  - Explicit "if you emit `steps`, it supersedes `instructions`" instruction.
- `_parse_ai_response` (`:274–309`) gains a `steps` parser:
  - If `data.get("steps")` is a non-empty list, emit structured step dicts on the returned `ExtractedRecipe` via a new `steps` attribute (dict list, not `ExtractedStep` instances — simpler, mirrors the ingredient-dict pipeline).
  - If `steps` is absent or empty, fall back to emitting `instructions` as today.
  - `ExtractedRecipe` dataclass (`base.py`) gets a new `steps: list[dict] | None = None` field; `ExtractedStep` dataclass stays unmodified — **not used in v1**, kept for future typed-step work.
- No vision-extractor changes in this epic. Vision path already produces `ExtractedRecipe.steps` differently (if at all); timers coverage for vision is a future follow-up noted in Non-Goals.

**Modified:** `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py:133–155`
- The existing `steps` path (`:134`) already reads `step_data.get("order", 1)` and `step_data.get("instruction", "")`. Extended to also read `step_data.get("timers", [])`.
- **Inline clamp + filter before persist:**
  ```
  raw_timers = step_data.get("timers") or []
  clean_timers = []
  dropped = 0
  for t in raw_timers[:10]:           # cap at 10 per step
      if not isinstance(t, dict): dropped += 1; continue
      dur = t.get("duration_minutes")
      if not isinstance(dur, int) or not (1 <= dur <= 360): dropped += 1; continue
      label = t.get("label", "")
      if not isinstance(label, str): label = ""
      clean_timers.append({"duration_minutes": dur, "label": label[:40].strip() or "timer"})
  if len(raw_timers) > 10: dropped += len(raw_timers) - 10
  ```
- Pass `timers=clean_timers` to `RecipeStep(...)`.
- When `dropped > 0`, write one audit row via a new helper `_log_timer_clamp(item, step_index, dropped)` that mirrors the `advance_recurrence_windows._log_audit` pattern: independent `db.commit()` in try/except so the audit row survives even if the main transaction rolls back. Tag: `service="worker", error_type="TimerClamp"`. Payload: JSON with `recipe_name`, `step_order`, `dropped_count`, `raw_input_sample`.

**Modified:** `services/api/src/api/v1/recipe/get_recipe.py` — comment-only: note at `:66–79` that `StepResponse.timers` is populated by the AI extractor as of this epic.

**Eval fixtures and metric** — see Story cmt-3. Fixtures are **not restructured** from `instructions: string` to `steps: array`; instead, eval is at **recipe-level multiset** (see the story for details).

## Infrastructure changes

None. Rationale: no new AWS resources, no new migrations (column already exists), no new env vars, no CI workflow changes. The eval run continues to use the existing GitHub Actions job and the existing OpenAI key.

## Design principles

- **Three sources, one timer API.** Extracted, regex'd, and manual timers all construct the same `_ActiveTimer` and run through `_startTimer`. There is no source-tag; the user can't tell where a timer came from.
- **Hybrid is fallback, not merge.** When a step has any `timers` from extraction, the regex is not consulted. This avoids double-counting and keeps the predicted set deterministic.
- **Graceful degradation, not graceful failure.** Malformed extractor output is filtered, not rejected. Malformed frontend data is skipped, not crashed. The header button is always there.
- **Passive waits are not timers.** "Rest overnight" does not become a running countdown. The prompt excludes; the clamp catches anything over 360 min anyway.
- **Measure, don't gate.** The eval metric is measured and reported; it doesn't block merges in v1. Hard-gating a UX nicety on extraction metrics creates cascading merge pain.
- **No backfill.** Legacy recipes use the regex + manual path. A backfill script remains possible later but is out of scope.
- **Minimal touch on existing type layer.** `ExtractedStep` dataclass stays unused in v1; we pipe dicts through. Typed-step refactor is a separate future epic if ever needed.

## File structure

Anticipated touched paths:
- **Backend (libraries + services)**
  - `libraries/utils/utils/schemas/recipe_extraction_schema.py`
  - `libraries/utils/utils/services/recipe_extractors/base.py` (`ExtractedRecipe` gets `steps: list[dict] | None`)
  - `libraries/utils/utils/services/recipe_extractors/ai_extractor.py` (prompt + parser)
  - `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` (clamp + audit helper)
  - `libraries/utils/tests/unit/services/recipe_extractors/test_ai_extractor.py` (extend)
  - `libraries/utils/tests/unit/tasks/import_tasks/test_create_recipe_task.py` (extend)
  - `services/eval/evaluators/recipe_extraction_evaluator.py` (new metric)
  - `services/eval/tests/test_recipe_extraction_evaluator.py` (extend)
  - `services/eval/fixtures/expected/*.json` — **3+ fixtures extended with a new recipe-level `expected_timers` field** (see cmt-3 for exact fixture picks; no restructuring of `instructions` string).
  - `services/api/src/api/v1/recipe/get_recipe.py` (comment only)
- **Flutter**
  - `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
  - `app/lib/features/recipes/cook_mode/widgets/manual_timer_sheet.dart` (NEW)
  - `app/lib/features/recipes/cook_mode/widgets/step_timers_row.dart` (NEW)
  - `app/lib/features/recipes/cook_mode/util/timer_regex.dart` (NEW, exports `StepTimer` + `extractTimers`)
  - `app/lib/features/recipes/cook_mode/util/cook_timer_token.dart` (NEW)
  - `app/test/cook_mode_test.dart` (extend — `_steps` is now `_StepData`)
  - `app/test/cook_mode_gesture_test.dart` (extend if it constructs step fixtures)
  - `app/test/cook_mode_timer_test.dart` (extend — extracted + regex + manual paths; offline visibility)
  - `app/test/step_timers_row_test.dart` (NEW)
  - `app/test/manual_timer_sheet_test.dart` (NEW)
  - `app/test/timer_regex_test.dart` (NEW)

## Stories

### Story cmt-1 — Extraction schema + AI prompt + `ExtractedRecipe.steps` parsing

**AC1** — `recipe_extraction_schema.py` adds `steps: array<{order: int, instruction: string, timers: array<{duration_minutes: int, label: string}>}>` to the top-level schema. `instructions: string` is retained for backward compatibility. Manual validator accepts both.
**AC2** — `ai_extractor.py` prompt is extended with (a) the `steps` schema fragment, (b) the actively-tended rule, (c) a positive example ("Simmer for 10 minutes, stirring." → `timers: [{duration_minutes: 10, label: "simmer"}]`), (d) a negative example ("Let dough rise overnight." → `timers: []`), (e) the "if you emit `steps`, it supersedes `instructions`" rule.
**AC3** — `ExtractedRecipe` (`base.py`) gains `steps: list[dict] | None = None`; `ExtractedStep` dataclass is unchanged and unused in v1 (documented as such in a short doc-comment).
**AC4** — `_parse_ai_response` populates `ExtractedRecipe.steps` when the model returns a non-empty `steps` list; falls back to `instructions` only when `steps` is absent or empty.
**AC5** — Unit test: mock AI response with `steps: [{order:1, instruction:"Simmer 10 min", timers:[{duration_minutes:10, label:"simmer"}]}]` produces `ExtractedRecipe.steps` with exactly that shape.
**AC6** — Unit test: mock AI response with only `instructions: "…"` and no `steps` produces `ExtractedRecipe.instructions` populated and `ExtractedRecipe.steps = None`.
**AC7** — Unit test: mock AI response with `steps: [{timers: [{"duration_minutes": "25", "label": "bake"}]}]` (string not int) — the parsed result passes through (filtering happens in cmt-2 at persist time; schema is permissive).
**AC8** — No changes to `create_recipe_task` in this story — purely the extraction-side parsing.
**AC9** — Coverage: 100% on `services/api` maintained (note: extractor code is in `libraries/utils/`, which has its own coverage track — add tests to the matching path).

### Story cmt-2 — Persist timers in create_recipe_task with clamp + independent audit

**AC1** — `create_recipe_task.py:134–155`'s existing structured-steps path reads `step_data.get("timers", [])`, applies the clamp-and-filter logic specified in the "Backend changes" section above, and passes `timers=clean_timers` to `RecipeStep(...)`.
**AC2** — The clamp logic: capped at 10 entries per step; `duration_minutes` must be `int` in `[1, 360]`; `label` coerced to `str`, truncated to 40 chars, stripped; empty/missing label defaults to `"timer"`.
**AC3** — When any entry is dropped (wrong type, out-of-range, past cap), a new helper `_log_timer_clamp(item, step_order, dropped_count, raw_input_sample)` writes a `service="worker", error_type="TimerClamp"` audit row via an **independent `db.commit()` in try/except** — pattern copied from `advance_recurrence_windows._log_audit`. The audit row survives even if the main import transaction rolls back.
**AC4** — Unit test: import a recipe where step 1 has `timers: [{duration_minutes: 15, label: "simmer"}]`. Assert: `RecipeStep.timers` equals `[{"duration_minutes": 15, "label": "simmer"}]`; `GET /v1/recipes/{id}` returns that exact JSON.
**AC5** — Unit test: import with 12 timer entries including 2 out-of-range and 2 wrong-type → persisted `timers` has 8 entries (10 cap minus 2 filtered within the cap, plus 0 of the 2 truncated); one audit row written with `dropped_count=4`.
**AC6** — Unit test: all-invalid timers produces `RecipeStep.timers = []` and one audit row; import status is still `completed`.
**AC7** — Unit test: simulate a post-clamp exception before `db.commit()` — assert the audit row still persists (independent commit) and the main transaction rolled back.
**AC8** — `services/api` coverage stays at 100%.

### Story cmt-3 — Recipe-level timer eval metric + fixture extensions

**AC1** — **3 existing fixtures are extended with a new top-level `expected_timers: [{duration_minutes: int, label: str}]` field** (recipe-level multiset — all timers across all steps, no per-step binding). Fixtures are NOT restructured from `instructions: string` to `steps: array`. Picks are:
  - `simple_pasta.json` — one timer recipe; `expected_timers: [{duration_minutes: 2, label: "boil"}]` (or closest match to the fixture's existing text — verify before committing).
  - One multi-timer recipe (read `chicken_tikka_masala.json`, `potato_quiche.json`, any `*_batch_*.json`; pick the one with at least 3 timers across the instructions).
  - One genuine no-timer recipe (read fixtures until one is found that has no actionable duration; if none exist, skip this and use two multi-timer fixtures instead).
**AC2** — `recipe_extraction_evaluator.py` adds a `timer_extraction_f1` metric. Computation:
  - Gather predicted timers recipe-level: walk the predicted `steps[].timers` (or, if only `instructions` present, run the Dart regex equivalent in Python — OR just treat as empty set; decision: **empty set** for v1 simplicity).
  - Gather expected from the new `expected_timers` field.
  - Pair each predicted with the best-matching expected by:
    - **Duration match:** exact OR `|pred - exp| / exp ≤ 0.2`.
    - **Label similarity:** `difflib.SequenceMatcher(None, pred_label.lower(), exp_label.lower()).ratio() >= 0.6`.
    - Both required for a match.
  - Greedy 1-1 matching (each expected timer matches at most one predicted).
  - Precision = matched / predicted_count; Recall = matched / expected_count; F1 = harmonic mean.
  - Aggregate F1 by averaging across fixtures.
**AC3** — Metric surfaces in the existing eval report output alongside `ingredient_f1`/`struct_metrics`.
**AC4** — Unit test: synthetic evaluator input with 3 expected timers, 2 predicted (1 exact match, 1 duration-within-20%-label-match, 0 unmatched) → F1 around 0.80. Pin the expected value with a 0.05 tolerance.
**AC5** — **Soft gate only** — the metric is reported; no CI merge-block. A commented-out hard-gate at `max(0.7, baseline + 0.1)` is left in place with a TODO referencing a future hardening epic.
**AC6** — **Regression guard:** the story's merge run also records `ingredient_f1` and other existing metrics on the three extended fixtures. A manual review comment in the PR confirms existing metrics did not drop by more than 2 percentage points (no CI enforcement in v1 — soft-flag only).
**AC7** — First post-merge eval run records the baseline `timer_extraction_f1` number in the eval results; add a one-line comment to the evaluator code recording the baseline so the TODO hard-gate can be calibrated later.

### Story cmt-4 — Flutter: render step.timers, upgraded regex fallback, step_timers_row widget

**AC1** — `cook_mode_screen.dart` `_populateFromData` transforms `_steps` from `List<String>` to `List<_StepData>` (internal record with `instruction` + `timers`). Defensive JSON parsing: `null`, missing key, non-list, and malformed per-entry values all safely normalise to `timers: []`.
**AC2** — Rendering rule — **hybrid is fallback, not merge**: if `_currentStep._StepData.timers` is non-empty, render its buttons and do NOT consult the regex. Regex fires only when the structured list is empty/null/missing.
**AC3** — `timer_regex.dart` exposes `List<StepTimer> extractTimers(String instruction)` with: input capped at 2000 chars; multi-match via `allMatches` (max 10); ranges (lower bound + `rangeUpperLabel`); decimals; alias tokens; returns empty list (not null) when nothing matches.
**AC4** — `timer_regex_test.dart` table-drives at least 14 cases: single min, single hour, single sec, multi-in-one-step, range with dash/en-dash/"to", decimal hour, decimal min, alias `h`/`hr`/`m`/`min`/`s`/`sec`, empty string, whitespace-only, 2000-char input doesn't hang, malformed duration ("two minutes") returns empty.
**AC5** — `step_timers_row.dart` takes `List<StepTimer>`, renders each as an `OutlinedButton.icon` inside a horizontally-scrollable `SingleChildScrollView`. Button label is the concise form (`"${duration} min ${label}"` or `"${duration} min"` when label is the default). `Tooltip.message` surfaces `rangeUpperLabel` when set (e.g., "3–5 min in recipe"). Uses `_resolveCookTimer(context)` for colour.
**AC6** — `cook_timer_token.dart` defines `Color _resolveCookTimer(BuildContext context)` — returns `context.cookModeTheme.cookTimer` when the extension is registered, `Theme.of(context).colorScheme.tertiary` otherwise. Single source; both widgets use it.
**AC7** — Widget test: step with `timers: [{durationMinutes: 3, label: "simmer"}, {durationMinutes: 10, label: "bake"}]` renders two buttons with labels "3 min simmer" / "10 min bake".
**AC8** — Widget test: step with `timers: []` and instruction `"Bake 25 minutes, rotate at 12 minutes"` renders two buttons via regex (25 min, 12 min).
**AC9** — Widget test: **hybrid-not-merge** — step with `timers: [{durationMinutes: 3, label: "simmer"}]` AND instruction `"Simmer 3 min then bake 25 min"` renders **exactly one button** ("3 min simmer"); the regex is not consulted.
**AC10** — Widget test: step with `timers: []` and instruction `"Let rise until doubled"` renders zero inline buttons (the header button is asserted present in cmt-5).
**AC11** — Widget test: step with `timers: [{"duration_minutes": "25"}]` (wrong type — simulating a bad wire-level payload) normalises to `timers: []` and falls back to regex path; no crash.

### Story cmt-5 — Flutter: manual timer header button + ManualTimerSheet

**AC1** — `cook_mode_screen.dart` `_buildHeader` includes a new `IconButton(Icons.timer_outlined, tooltip: "Add a timer", onPressed: _showManualTimerSheet, constraints: const BoxConstraints(minWidth: 48, minHeight: 48))` between the AI chat button (`:600`) and the cooking-time pill (`:626`). **48×48 tap target** (meets AA minimum; fits the 360dp header without crushing the title).
**AC2** — `manual_timer_sheet.dart` is a `showModalBottomSheet` with: a numeric text field (`TextInputType.number`, `inputFormatters: [FilteringTextInputFormatter.digitsOnly]`, `suffixText: "min"`); validates `minutes ∈ [1, 360]`; a label text field (`maxLength: 40`, default text "Timer"); a "Start" `FilledButton` disabled when validation fails. Uses `_resolveCookTimer(context)` for accents.
**AC3** — Submitting calls back with `(int minutes, String label)`; cook mode invokes `_startTimer(Duration(minutes: n), _disambiguateTimerLabel(label))` — no new path.
**AC4** — `_disambiguateTimerLabel(requested)` — scans `_activeTimers` for exact-match labels; if any, appends `" 2"`, `" 3"`, etc. until unique. So two "Timer" entries become "Timer" + "Timer 2". Unit tested.
**AC5** — Manual-added timer appears in the active-timers row identically to extracted/regex timers; completes with the same notification, snackbar, and haptic. No source badge / source distinction visible anywhere.
**AC6** — `manual_timer_sheet_test.dart` covers: valid 15-min entry starts a timer; 0-min entry blocks Start; 400-min entry blocks Start; paste of "40abc" on submit is rejected (filtered); empty label falls back to "Timer"; 41-char label is truncated/rejected.
**AC7** — Widget test in `cook_mode_timer_test.dart`: pump `CookModeScreen` with `_isOffline = true` — assert the timer header icon is still **visible and tappable** (unlike the AI chat button which hides when offline, the manual timer icon persists).
**AC8** — Widget test: tap header timer icon → sheet opens → enter 3 min "Timer" → Start → active-timers row shows "Timer" chip. Tap again → enter 5 min "Timer" → Start → chip shows "Timer 2" (disambiguated).

### Story cmt-6 — End-to-end widget regression sweep

**AC1** — Full `cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart` suite runs green after cmt-4 and cmt-5 — all Epic 6 ACs preserved.
**AC2** — Integration-style widget test: mount `CookModeScreen` with mocked recipe having one step with `timers: [{simmer, 3}]` — assert button renders ("3 min simmer"), tap starts timer, OS notification scheduled (mocked), fake-async advance 3 min → snackbar appears.
**AC3** — Integration-style widget test: mount with legacy recipe (no structured timers, "Bake 25 min" instruction) — assert regex path renders the button, tap → timer starts.
**AC4** — Integration-style widget test: empty `timers` + "rise until doubled" instruction — assert zero inline buttons and header icon button present; tap header → sheet → enter 45 → start → active-timers row.
**AC5** — Integration-style widget test: **hybrid** — structured `[{simmer, 3}]` + instruction "Simmer 3 min then bake 25 min" — assert exactly one button ("3 min simmer"), regex not consulted.
**AC6** — Manual QA checklist in the story's walkthrough file: all three paths exercised on a real device/emulator + the hybrid path. Note which recipes in the dev/staging DB have vs. don't have `step.timers` populated (helps repro Paths A and B deterministically).

## Dependencies

- **Internal ordering:**
  - `cmt-1 → cmt-2`: persistence depends on the extractor emitting `steps: [{timers: [...]}]`. cmt-1 without cmt-2 is inert (extractor emits the field; nothing persists it).
  - `cmt-1 → cmt-3`: evaluator runs against parsed extraction output (or the `expected_timers` field; see AC2).
  - `cmt-1, cmt-2` (backend) can land **before or after** `cmt-4, cmt-5` (flutter). Backend-first means new imports populate `step.timers` by the time flutter ships; flutter-first ships the regex + manual paths immediately and upgrades silently when backend lands.
  - `cmt-6` depends on cmt-4 and cmt-5.
- **Cross-epic (soft, from party-mode):**
  - `epic-cook-mode-polish`'s cmp-1 defines the `cookTimer` token consumed here. This epic's `_resolveCookTimer` helper falls back to `colorScheme.tertiary` when cmp-1 hasn't landed yet — so either epic can ship first. Once both are in, the timer accent picks up `cookTimer` automatically.
  - **Merge risk:** cmt-5 adds an `IconButton` inside `_buildHeader`. cmp-2 also edits `_buildHeader` (replaces `colorScheme.primary` bg with `cookSurface`). Whichever ships second will need to reconcile the other's header edit. Low-risk because the edits are in different parts of the Row.

## Non-Goals (scoped out for this epic)

- **No backfill** for existing recipes (locked per user Q4). Legacy recipes keep `step.timers = []` and use regex + manual.
- **No vision-extractor timer support.** Vision path (`vision_extractor.py`) is not touched. Recipes imported from photos get regex + manual paths only. A follow-up epic can add vision coverage.
- **No step-level eval metric.** Eval is recipe-level multiset in v1; step-level binding is deferred to a future epic (would require restructuring `instructions: string` fixtures into a `steps: [...]` array across all evaluators — non-trivial schema change).
- **No `ExtractedStep.from_dict`.** The dataclass stays unused. If a future epic wants typed steps, that's its job.
- **No timer editing** (reschedule, rename, change duration of an already-running timer). Only cancel + restart, as today.
- **No cross-device timer sync.** Timers are single-device, as today.
- **No passive-wait-time UI.** "Marinate 4 hours" does not become a timer or a recipe-level warning in v1.

## Open questions for the user

None at refinement time. Three party-mode questions (extractor arch / header layout / eval scope) were resolved autonomously with defensible sensible-default picks, documented in the Non-Goals and Design Principles sections. If any of those turn out to matter more than expected (e.g., step-level eval precision becomes important), they spawn follow-up epics rather than blocking this one.
