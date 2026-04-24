<!-- refined via party-mode 2026-04-20 -->
# Epic: Cook Mode Polish (Flutter-only)

## Overview

Cook Mode (Epic 6) ships a working cooking experience but dogfood surfaced three UX regressions that make the feature feel unfinished: (1) the scaffold force-applies `AppTheme.dark()` and uses `colorScheme.primary` (terracotta) as a large background fill, so cook mode feels "everything is orange" and creates a hard seam when entering from a light app screen; (2) navigating **back** to a prior step still renders it with a line-through + green-border "completed" visual because `_completedSteps` is never cleared; (3) the chat-sheet input row uses `primary` as its background, creating a colour discontinuity inside the sheet. The ingredient toggle strip works well and is explicitly preserved.

This epic is Flutter-only. No backend, no schema, no infra.

## Goal

Cook mode inherits the app's ambient theme (light, dark, or system) with a single cohesive palette defined in a new `CookModeTheme` `ThemeExtension`, and the "completed" visual only shows for steps the user has actually walked past. Entering cook mode from the home screen feels like entering a polished mode of the same app, not a different app.

## End-user flow

1. User opens a recipe on the **home screen in light theme**.
2. User taps **"Cook"**.
3. Cook mode opens in **light theme** — calm surface colour, orange reserved for the Next button and active-timer ring only. No jarring switch. Loading spinner + error fallback also render in the cook palette (no "orange wall" even when a recipe fails to load).
4. User swipes forward through steps 1 → 2 → 3 → 4; departing steps get a green check in the step-pill strip.
5. User realises they forgot something on step 2 and **swipes back** (or taps the step-2 pill).
6. Step 2 renders as the **current in-progress step** — not crossed out, not dimmed. The step-2 pill shows as "current" (no green check). Steps 3 and 4 are still crossed out in the pill strip (they did walk past those).
7. User swipes forward again; step 3 renders normally (not as "completed" — they're on it). Step 2 pill re-adds its green check once they advance.
8. User opens the **AI chat sheet** from the header — the sheet's background blends with the cook palette; the input row + the assistant message bubbles blend, no orange seam. Chat sheet pumped on dark re-enters dark.
9. User goes offline mid-cook — offline indicator uses a calm `cookOffline` tone, not raw terracotta.
10. User completes cooking; **post-cook feedback** sheet appears in the same palette; user rates and exits.
11. User toggles system theme to dark and re-enters cook mode from the same recipe — same spatial layout, same contrast ratios, no flash of the stale palette, no forced-dark override.

## Frontend changes

**New file:** `app/lib/core/theme/cook_mode_theme.dart` — `CookModeTheme extends ThemeExtension<CookModeTheme>` with tokens:

| Token            | Role                                               |
|------------------|----------------------------------------------------|
| `cookSurface`    | Scaffold, header, sheet backgrounds                |
| `cookSurfaceDim` | Step card background, upcoming-step pill           |
| `cookOnSurface`  | Default body + heading text                        |
| `cookAccent`     | Next button, progress bar fill, current-step pill  |
| `cookOnAccent`   | Text/icons drawn on `cookAccent`                   |
| `cookProgress`   | Linear progress indicator fill                     |
| `cookCompleted`  | Completed-step pill + completed-card border + checked ingredient chip |
| `cookOnCompleted`| Text/icons drawn on `cookCompleted`                |
| `cookTimer`      | Active-timer pill, timer detail countdown, inline timer button (also consumed by `epic-cook-mode-timers`) |
| `cookError`      | Error-scaffold banner, retry button                |
| `cookOffline`    | Offline indicator (icon + "Offline" label)         |
| `cookDivider`    | 1-px dividers, chip borders                        |
| `cookShadow`     | BoxShadow colour (StepNavigator, sheets)           |

Follows the `PalatefulColors`/`ImportStateColors` pattern in `app/lib/core/theme/` — `copyWith`, `lerp`, `light()` and `dark()` factories. `lerp` uses `Color.lerp(a, b, t)!` on each token. Register on both `AppTheme.light().extensions` and `AppTheme.dark().extensions` in `app_theme.dart`. Convenience getter `BuildContext.cookModeTheme` (mirrors `ImportStateColors`'s getter pattern).

**Modified:** `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- Remove the `Theme(data: darkTheme, child: Builder(...))` wrap (`:445–568`). Replace with a single `Builder` that reads `Theme.of(context)` + `context.cookModeTheme`.
- Loading scaffold (`:453–458`) → `cookSurface` bg, `cookAccent` spinner.
- Error scaffold (`:461–499`) → `cookSurface` bg, `cookError.withAlpha(…)` banner tint, `cookError` on retry button.
- Main scaffold (`:502–566`) → `cookSurface` bg.
- Header (`:574`) → `cookSurface` bg.
- Offline indicator (`:615, 619`) → `cookOffline` (was `colorScheme.tertiary`).
- Step-content card (`:794–829`): normal state → `cookSurfaceDim` bg + `cookDivider` border; completed state → `cookCompleted.withAlpha(0.15)` bg + `cookCompleted` border + `cookOnCompleted` for the check icon.
- Instruction text colour: normal → `cookOnSurface`; completed → `cookOnSurface.withAlpha(0.6)` with line-through.
- **Current step never renders completed visuals**: line-through, dim alpha, check icon, and completed border are gated on `_completedSteps.contains(_currentStep) && /* renders-as-completed */` **where "renders-as-completed" is false when the index is `_currentStep`**. Concretely: `_buildStepContent` reads a local `final bool showAsCompleted = _completedSteps.contains(_currentStep) && /* never true for current */ false;` — i.e., the current step's card always renders the in-progress visual. Completed visuals exist only in the StepNavigator pill row for non-current indices.
- Progress bar colour → `cookProgress` (was `onSurface`).
- Active timer pill — bg `cookTimer.withAlpha(0.15)`, border/text/ring `cookTimer`.
- Inline "Set timer" button — `cookTimer` foreground + border.
- Snackbar on timer-complete — `cookCompleted`.
- Modal-sheet `backgroundColor:` overrides at `:397` (post-cook feedback) and `:422` (timer detail) → `cookSurface` (was `colorScheme.surfaceContainerLow`).
- `_goToStep(int step)` — when `step < _currentStep`, remove `step` from `_completedSteps` **before** updating `_currentStep`. Keep the existing haptic + bounds check.

**Modified:** `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart`
- Replace `colorScheme.primary` (current pill fill, `:100`; `_NavButton` isPrimary, `:177`) with `cookAccent`.
- Replace `appColors.success` (completed pill fill, `:102, 109`) with `cookCompleted`.
- Replace `colorScheme.surfaceContainerHighest` (upcoming pill, `:103`; `_NavButton` surface, `:179`) with `cookSurfaceDim`.
- Numeral text colour on current pill (`:126`) → `cookOnAccent` (was `colorScheme.surface`).
- Check icon colour on completed pill (`:118`) → `cookOnCompleted` (was `colorScheme.surface`).
- Shadow (`:40`) → `cookShadow`.
- A pill renders "completed" only if `index != currentStep && completedSteps.contains(index)` — the current pill never shows a check, independent of set membership.
- `Semantics` node on each pill updates on state change so TalkBack/VoiceOver announce when a step switches from "completed" to "current" (step back) or vice versa.

**Modified:** `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart`
- Tokens only: `appColors.success` (checked chip bg, `:183–191`) → `cookCompleted`; checked-chip text/icon colour (`:203, 216, 253, 260`) → `cookOnCompleted` (was `colorScheme.surface`); `appColors.textTertiary` (header labels, `:49`) → `cookOnSurface.withAlpha(0.7)`; `colorScheme.outlineVariant` (chip borders, `:110`) → `cookDivider`; counter-badge text → `cookAccent`.
- **No behaviour or layout changes.** Compact/expanded cross-fade, haptic feedback, counter badge, strikethrough on checked — all identical.

**Modified:** `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart`
- Input row background at `:269` → `cookSurface` (was `primary`). Add a `cookAccent` focus outline on the `TextField` via `InputDecoration.focusedBorder`.
- Assistant message bubble background at `:409` → `cookAccent.withAlpha(0.12)` (was raw `primary`).
- Divider at `:233` → `cookDivider`.
- Send button — keep filled but use `cookAccent` + `cookOnAccent` for icon.

**Modified:** `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart`
- Token migration only; no behaviour change.

**Removed:** Any `Theme(data: AppTheme.dark(), …)` usage inside `cook_mode/**`.

## Backend changes

None. This epic is strictly Flutter. Rationale: `CookModeTheme` lives in the client app; the recipe-steps API contract is unchanged; no persistence of cook-mode state.

## Infrastructure changes

None. Rationale: no env vars, no Terraform, no container, no migration, no secret, no colour assets (all tokens defined in Dart const).

## Design principles

- **One palette source.** `CookModeTheme` is the only place cook-mode colour choices live. Direct `colorScheme.*` / `appColors.*` references inside `cook_mode/**` get grep'd out and replaced — the gate is enforced in cmp-3 AC5.
- **Tokens have intent, not appearance.** `cookAccent` can map to terracotta in dark and deep-orange in light — callers don't care. Callers say what role the colour plays ("this is the progress bar"), not what colour it is.
- **Completion is departure.** A step is "done" only once the user has walked past it. Being in the `_completedSteps` set is a necessary but not sufficient condition — the current step, by definition, isn't a completed step yet. Current step never renders as completed, period.
- **WCAG AA is a precondition, not a follow-up.** Contrast ratios are checked and documented when the palette is picked (cmp-1 AC7) — not deferred to post-merge visual QA.
- **Don't regress the ingredient strip.** The one widget the user explicitly likes gets token migration and nothing else.
- **Colour-value widget tests, not goldens.** The repo has no golden-test infra today (`app/test/**` has zero `matchesGoldenFile` references). Introducing goldens now adds CI + font-determinism overhead for minimal incremental signal. Assert `Color` values directly on key surfaces; catches exactly the regressions this epic is about.

## File structure

Anticipated touched paths:
- `app/lib/core/theme/cook_mode_theme.dart` (NEW)
- `app/lib/core/theme/app_theme.dart` (register extension)
- `app/lib/core/theme/theme.dart` (barrel export)
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/widgets/step_navigator.dart`
- `app/lib/features/recipes/cook_mode/widgets/ingredient_strip.dart`
- `app/lib/features/recipes/cook_mode/widgets/cook_mode_chat_sheet.dart`
- `app/lib/features/recipes/cook_mode/widgets/post_cook_feedback_sheet.dart`
- `app/test/cook_mode_theme_test.dart` (NEW)
- `app/test/cook_mode_test.dart` (extend)
- `app/test/cook_mode_gesture_test.dart` (extend — untoggle-on-back coverage)
- `app/test/cook_mode_timer_test.dart` (extend — offline-indicator token)
- `app/test/cook_mode_chat_sheet_test.dart` (extend)
- `app/test/step_navigator_test.dart` (extend)
- `app/test/ingredient_strip_test.dart` (extend)

## Stories

### Story cmp-1 — CookModeTheme ThemeExtension scaffold

**AC1** — `cook_mode_theme.dart` defines `CookModeTheme extends ThemeExtension<CookModeTheme>` with all 13 tokens listed in the Frontend-changes table above, plus `copyWith` and `lerp`.
**AC2** — Two factories: `CookModeTheme.light()` and `CookModeTheme.dark()`. Dark preserves the existing terracotta/cocoa/sage identity but separates `cookSurface` (cocoa) from `cookAccent` (terracotta) — no more primary-as-background. Light uses a warm-neutral `cookSurface` (off-white, warm undertone) + deep-orange `cookAccent` + sage `cookCompleted`.
**AC3** — Registered on both `AppTheme.light().extensions` and `AppTheme.dark().extensions` in `app_theme.dart`. Follows the registration pattern of `ImportStateColors`.
**AC4** — `BuildContext.cookModeTheme` convenience getter returns the extension. On a missing extension, falls back to `CookModeTheme.light()` (mirrors `ImportStateColors`'s test-pump-safe fallback); a debug-only `assert` warns so prod test setups don't silently skip real registration.
**AC5** — Unit test: `Theme.of(context).extension<CookModeTheme>()` is non-null under both `AppTheme.light()` and `AppTheme.dark()`, and each token resolves to a distinct `Color` (no accidental duplication).
**AC6** — No existing cook-mode widget is modified in this story. This is the scaffold — migration happens in cmp-2 and cmp-3.
**AC7** — WCAG AA contrast documented in the `cook_mode_theme.dart` doc-comment: every text-on-surface pair (`cookOnSurface` on `cookSurface`, `cookOnAccent` on `cookAccent`, `cookOnCompleted` on `cookCompleted`) meets ≥4.5:1 for normal text; every UI-component pair (pill-border on surface, divider on surface) meets ≥3:1. Ratios calculated and stated for both light and dark factories. A unit test asserts the ≥4.5:1 / ≥3:1 thresholds numerically for at least the three text-on-surface pairs.

### Story cmp-2 — Migrate cook_mode_screen.dart to CookModeTheme + drop forced-dark wrap

**AC1** — `Theme(data: AppTheme.dark(), …)` wrap in `cook_mode_screen.dart:445–568` is removed. The screen reads `Theme.of(context)` + `context.cookModeTheme`.
**AC2** — Scaffold (`:503`), header (`:574`), loading scaffold (`:454`), error scaffold (`:463–499`), step-content card (`:794–829`), active-timers row (`:662–721`), progress bar, inline timer button, and snackbar all use `CookModeTheme` tokens as spec'd in "Frontend changes" above. Zero `colorScheme.primary` references remain in this file.
**AC3** — `_buildStepContent` rendering: line-through text, 0.6-alpha dimming, check icon, and completed-card border render **only when the step being rendered is not `_currentStep`**. Since `_buildStepContent` only renders the current step today, the completed-state branch inside it is deleted outright; completed visuals remain in StepNavigator pills (covered by cmp-3).
**AC4** — Offline indicator at `:615, 619` uses `cookOffline`. `wifi_off` icon + "Offline" text both adopt the token.
**AC5** — Modal-sheet `backgroundColor:` at `:397` (post-cook feedback) and `:422` (timer detail) → `cookSurface`.
**AC6** — Widget test: launching `CookModeScreen` under `AppTheme.light()` renders a Scaffold whose `backgroundColor == context.cookModeTheme.cookSurface` (resolved against light). Same under `AppTheme.dark()`. No force-override.
**AC7** — Widget test: entering cook mode does not flash a different theme on first frame (no two-phase paint).
**AC8** — Widget test: error-state scaffold paints `cookSurface` + `cookError` banner, not raw `colorScheme.primary` as before.
**AC9** — `_goToStep(int step)` removes `step` from `_completedSteps` when `step < _currentStep`, before updating `_currentStep`. Covered by cmp-4 ACs — noted here only because the edit touches this same file.
**AC10** — All existing Epic 6 tests (`app/test/cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart`) continue to pass unmodified.

### Story cmp-3 — Migrate sub-widgets (step_navigator, ingredient_strip, chat_sheet, post_cook_feedback_sheet)

**AC1** — `step_navigator.dart`: pills use `cookAccent` (current), `cookCompleted` (completed), `cookSurfaceDim` (upcoming). `_NavButton` isPrimary uses `cookAccent` + `cookOnAccent`; non-primary surface uses `cookSurfaceDim`. Shadow → `cookShadow`. Check icon on completed pill → `cookOnCompleted`; numeral on current pill → `cookOnAccent`. A pill renders "completed" only if `index != currentStep && completedSteps.contains(index)`.
**AC2** — `step_navigator.dart` pills emit `Semantics(label: '...current'|'...completed'|'...upcoming')` that changes on state transitions. A widget test asserts the semantic state change when advancing past a step and then returning to it.
**AC3** — `ingredient_strip.dart` swaps colour tokens only: `cookCompleted` for checked chip bg, `cookOnCompleted` for checked text/icon, `cookOnSurface.withAlpha(0.7)` for header labels, `cookDivider` for chip borders, `cookAccent` for counter badge. Compact/expanded animation, haptic, counter, strikethrough behaviour identical. Existing `ingredient_strip_test.dart` passes unmodified.
**AC4** — `cook_mode_chat_sheet.dart` input-row background (`:269`) → `cookSurface`; TextField has a `cookAccent` `focusedBorder`; assistant message bubble background (`:409`) → `cookAccent.withAlpha(0.12)` (explicitly not raw `cookAccent`); divider (`:233`) → `cookDivider`; send button filled with `cookAccent` + `cookOnAccent` icon.
**AC5** — `post_cook_feedback_sheet.dart` tokens migrated; behaviour identical; its existing widget test passes.
**AC6** — Grep gate: `grep -rE "colorScheme\\.(primary|tertiary)" app/lib/features/recipes/cook_mode/` returns zero hits. Runs in CI as part of `npx nx run app:lint` (or a new `app:grep-cook-mode-tokens` target) — fails the build on any new violation.
**AC7** — Widget test: `CookModeChatSheet` pumped under `AppTheme.light()` renders the sheet with `cookSurface` background + light-palette assistant bubbles; same under `AppTheme.dark()` renders dark. Sheet inherits the ambient `MaterialApp` theme (no override needed — just verifying the absence of stale overrides from the force-dark era).

### Story cmp-4 — Step completion untoggle on back-navigation

**AC1** — `_goToStep(int step)` in `cook_mode_screen.dart` removes `step` from `_completedSteps` when `step < _currentStep` (before updating `_currentStep`).
**AC2** — Forward navigation via `_nextStep()` continues to add the departing step to `_completedSteps`.
**AC3** — `_markAllUpToHere()` semantics unchanged — it still adds all steps `[0, _currentStep]` in bulk.
**AC4** — `StepNavigator` pill rendering: a pill is "completed" iff `index != currentStep && completedSteps.contains(index)`. The current pill never renders a green check, regardless of set state. (Reinforces cmp-3 AC1.)
**AC5** — `_buildStepContent` — the current step's instruction text never renders with `TextDecoration.lineThrough` or 0.6-alpha dim, regardless of set membership. (Reinforces cmp-2 AC3.)
**AC6** — Widget test: advance 1 → 2 → 3 → 4 (departing 0, 1, 2, 3 → set `{0,1,2,3}`), then swipe back to 2. Assertions: (a) step-2 rendered text has no `lineThrough`; (b) pill at index 2 has no check icon; (c) pills at indices 0, 1, 3 still have check icons (step 3 was walked past, now walked back over partially); (d) pill at index 2 has "current" Semantics; (e) `_completedSteps` equals `{0, 1, 3}` after this flow.
**AC7** — Widget test: tap pill at index 0 from index 4 — assert: set collapses to `{1, 2, 3}` (4 was never added; 0 untoggled on back-tap); pill at index 0 shows "current" not "completed".
**AC8** — Widget test parameterised across **all three back-navigation routes**: (a) swipe-right (`onHorizontalDragEnd` velocity > 500 at `:531`), (b) left-zone tap (`tapX < screenWidth * 0.25` at `:541`), (c) StepNavigator pill-tap (`onStepTap(index)` at `:559`). All three must untoggle.

### Story cmp-5 — Colour-value widget tests + Epic 6 regression sweep

**AC1** — Widget test `cook_mode_theme_test.dart`: for both `AppTheme.light()` and `AppTheme.dark()`, assert each of the 13 `CookModeTheme` tokens resolves to the expected `Color` value (pinned in the test). Catches accidental drift.
**AC2** — Widget test `cook_mode_test.dart` extension: pump `CookModeScreen` under light, assert the Scaffold's `backgroundColor == context.cookModeTheme.cookSurface`, assert the progress bar's colour == `cookProgress`, assert the active-timer pill border colour == `cookTimer`, assert the StepNavigator current-pill colour == `cookAccent`. Repeat under dark.
**AC3** — Widget test: pump in the error-state path (stubbed `ApiClient` throwing) — scaffold bg == `cookSurface`, banner tint derived from `cookError`. Pump in the loading-state path — scaffold bg == `cookSurface`, spinner colour == `cookAccent`.
**AC4** — Regression sweep: `cook_mode_test.dart`, `cook_mode_gesture_test.dart`, `cook_mode_timer_test.dart`, `cook_mode_chat_sheet_test.dart`, `step_navigator_test.dart`, `ingredient_strip_test.dart` — all green after cmp-1..cmp-4 land.
**AC5** — Manual QA checklist (walkthrough file in the story): (a) open cook mode from light home, advance + back, confirm no orange scaffold; (b) open chat sheet under light, confirm no orange seam; (c) toggle system theme to dark, exit + re-enter same recipe, confirm cook mode repaints in dark (no stale light colours); (d) force error (kill network before entering), confirm error scaffold uses cook palette; (e) force loading (slow API stub), confirm loading scaffold uses cook palette; (f) go offline mid-cook, confirm offline indicator uses `cookOffline` not raw terracotta.
**AC6** — Accessibility: tap targets on new elements (none here — all additions are token-level). Existing 64×64 header icon buttons (`cook_mode_screen.dart:581, 604, 654`) preserved. VoiceOver/TalkBack regression: cmp-3 AC2 + cmp-4 AC6(d) cover the Semantics transitions.
**AC7** — Coverage: new token assertions add to the Flutter test suite; `npx nx run app:test` passes; no new lint errors.

## Dependencies

- **Internal:** cmp-1 blocks cmp-2 and cmp-3 (need the extension before migrating widgets). cmp-4 is logic-only and can land in parallel with cmp-3. cmp-5 depends on cmp-1 through cmp-4.
- **Cross-epic:**
  - `epic-cook-mode-timers` **soft-depends** on cmp-1: the `cookTimer` token is defined here and consumed there. Timers epic falls back to `colorScheme.tertiary` if the extension isn't registered yet — so timers work can still ship first, but will re-paint against `cookTimer` once cmp-1 lands.
  - Merge-risk note: the manual timer button (`epic-cook-mode-timers` cmt-5) lands inside `_buildHeader` which cmp-2 migrates. If timers ships first, its `_buildHeader` edit uses `colorScheme.primary`; cmp-2 then has to migrate the new IconButton alongside existing ones. Not a blocker; just a heads-up in the timers epic's dependencies section.

## Open questions for the user

None — all decisions locked at planning time. Party-mode flagged two stylistic trade-offs (goldens-vs-colour-value tests; WCAG AA as AC-vs-post-merge), both resolved to the sensible default in this refined draft (colour-value widget tests; WCAG AA as an AC).
