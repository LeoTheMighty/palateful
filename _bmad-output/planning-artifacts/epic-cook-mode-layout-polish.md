<!-- refined via party-mode 2026-04-22 -->
# Epic: Cook Mode Layout Polish (Flutter-only)

## Overview

Cook mode (both single-recipe and meal variants) has accumulated small layout inconsistencies that hurt legibility in the kitchen. The user verbatim: *"I can barely see the ingredients"* and *"we're a little strange with the padding."* This epic is a shared visual-polish pass that applies to both `CookModeScreen` and `MealCookModeScreen`. It prepares the ground for `epic-cook-mode-multi-recipe-flow` by simplifying the ingredient strip into a single always-expanded grouped grid (no more compact/expanded toggle) and removing affordances that no longer earn their keep.

This epic is **Flutter-only**. No backend, no schema, no infra. It also sits upstream of the multi-recipe-flow epic: the ingredient-strip simplification and the removed section-header-above-step-card are load-bearing for that epic's layout.

## Goal

Cook mode feels clean and legible at arm's length in the kitchen. Ingredient chip text is readable without squinting. The header has no redundant close affordance. Padding is consistent across the top-of-screen chrome. Recipe cook mode and meal cook mode share the same layout DNA for everything above the step card.

## End-user flow

1. User opens a recipe and taps **Cook**.
2. Cook mode opens. Top bar shows: back arrow · recipe name · manual-timer icon · (optional offline badge) · cooking-time badge · overflow menu. **No X button.** The old close X (cook_mode_screen.dart:1057–1062; meal_cook_mode_screen.dart:1237) is gone; back is the sole exit.
3. Directly below the top bar, the **active-timers row** (if any timers are running) — layout unchanged in this epic; chip copy bump (`Dressing · 0:17`) belongs to the multi-recipe epic.
4. Below that, the **full ingredient list, always expanded**. No `INGREDIENTS` ALL-CAPS header, no `Expand`/`Collapse` button, no `x / y` tiny counter in the header. Ingredients render as a generously-sized `Wrap` of chips. Chip typography: ingredient name at 14px w500, quantity at 14px w600 in `cookAccent`, checked-state using `cookCompleted` background + `cookOnCompleted` foreground.
5. **Scrolling behavior (locked).** The ingredient block sits inside the existing `SingleChildScrollView` that wraps the step column. **No height cap, no internal scroll region.** Rationale: the outer scroll view is already scrollable, a nested scroll parent would steal swipe gestures from the cook-mode 25/50/25 gesture zones, and the product decision is "surface the whole list." This is the trade-off the user accepted: tall ingredient sets push the step card below the fold on mount. We document this as an accepted edge case, not a defect.
6. **Empty-ingredient edge case (new).** If a recipe has zero ingredients, the strip renders **nothing** — no padding, no empty header, no "0 ingredients" label. The chain from the header being gone means there is no "Ingredients 0/0" scaffold anymore; a widget that renders nothing when empty is the cleanest outcome. Verified by an explicit test (see cmlp-2 AC).
7. **Loading / error edge case (meal mode).** When a component recipe hasn't loaded yet, the existing `ComponentLoadPlaceholder` path (`meal_cook_mode_screen.dart:1340`) still owns the whole step-card area. The ingredient strip is only mounted for ingredients that the `CookPlan` has already flattened. Groups for not-yet-loaded recipes simply don't appear until the recipe lands — consistent with today's behavior.
8. **Meal-mode specifics for this epic:** the ingredient list renders **grouped by component recipe** with per-group section headers. Header shape: `Dressing` in 13px w600 with 0.4 letter-spacing and `cookOnSurface` alpha 0.7, a `Divider(height:1)` in `cookDivider` alpha 0.5 below, then the group's chips. No `--- From Dressing ---` dashed dividers anymore. No per-chip source-tag pill (the group header replaces it). Untagged ingredients (builder returns null) render in a trailing `Other` group, same header treatment.
9. **No section header above the step card.** The `RecipeSectionHeader` render call at `meal_cook_mode_screen.dart:1358–1363` is removed entirely in this epic (not commented — see Design principles below for rationale). The widget file `recipe_section_header.dart` stays on disk; its deletion is deferred to the multi-recipe epic.
10. Bottom chrome: progress bar + step pills + Prev/Next/Done. Progress bar horizontal margin is tightened from 48 → 24 in both cook modes so the bar visually aligns with the step card's 24-padding.
11. **Dark / light / system theme:** the `CookModeTheme` extension continues to drive all tokens. Every surface and text color in this epic reads from it; no hard-coded palette values. Chip legibility verified in light + dark (`cookAccent` contrast against `cookSurfaceDim` ≥ 4.5:1 in both themes).
12. **Accessibility:** Dynamic Type scaling (`TextScaler`) continues to apply. The fixed chip width (`_IngredientChip.compactSize` 64/72) is replaced by a `ConstrainedBox` with `minWidth: 72, maxWidth: 160` so large text doesn't clip. Tap target stays ≥ 48×48 via chip padding + `Wrap.runSpacing`. Each meal-mode group-header gets `Semantics(header: true, child: ...)` so VoiceOver / TalkBack announce "Dressing, heading" before reading chips.

## Frontend changes

### `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`

- **Header row** (`_buildHeader`, lines 973–1083):
  - Remove the `IconButton` at lines 1057–1062 that renders `Icons.close` (the "Close button" comment block).
  - Re-tune header outer padding: `EdgeInsets.symmetric(horizontal: 8, vertical: 4)` → `EdgeInsets.fromLTRB(8, 4, 12, 4)` so the overflow menu doesn't hug the right edge.
- **Progress bar margin** (line 1119): `EdgeInsets.symmetric(horizontal: 48)` → `EdgeInsets.symmetric(horizontal: 24)` to match step card content padding (line 1135, currently 24 — unchanged).

### `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`

- Remove the mirror `Icons.close` IconButton at line 1237 in the meal-mode header builder. Apply the same `fromLTRB(8, 4, 12, 4)` outer padding.
- Progress bar margin at line 1369: 48 → 24.
- **Delete** the `RecipeSectionHeader` block at lines 1357–1364 (the `if (showSectionHeader) ... const SizedBox(height: 8)` wrapper **and** its unused `showSectionHeader` local at line 1350). No commented-out placeholder. Rationale: see Design principles.

### `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`

- **Remove state** `_isExpanded` (line 38) and the `AnimatedCrossFade` wrapping logic (lines 108–115). Always render the expanded Wrap layout. Confirmed safe: grep shows no other cook-mode widget reads `_isExpanded` or subscribes to the `AnimatedCrossFade`'s a11y events; the only consumers are the two test files listed below.
- **Remove the header row** entirely (lines 52–105): no `INGREDIENTS` label, no `x/y` counter, no Expand/Collapse `GestureDetector`.
- **Remove `_buildHorizontalStrip`** method (lines 121–144) and the `isCompact` branch inside `_IngredientChip` (lines 268–345).
- **If `widget.ingredients.isEmpty`**, return `const SizedBox.shrink()` (new — protects the empty-ingredient edge case).
- **Refactor `_buildExpandedGrid`** into the sole layout method:
  - For recipe mode (no `sourceTagBuilder`): `Padding(EdgeInsets.fromLTRB(16, 12, 16, 16))` wrapping a `Wrap(spacing: 8, runSpacing: 8, children: chips)`.
  - For meal mode (`sourceTagBuilder != null`): group ingredients by `sourceTagBuilder(index)` value. Emit one `Column` child per group: a group-header widget + `Wrap(chips)`. Group-header shape: `Padding(EdgeInsets.fromLTRB(16, 16, 16, 4))` wrapping `Semantics(header: true, child: Column([Text(name, style: 13px w600 letterSpacing 0.4 color cookOnSurface.alpha(0.7)), SizedBox(4), Divider(height: 1, color: cookDivider.alpha(0.5))]))`. Untagged chips trail in a group whose header reads `Other` iff the untagged set is non-empty.
  - **Keep** `Key('ingredient_group_$rawTag')` on the outer group container (and `Key('ingredient_group_untagged')` on the Other group). Test semantics are preserved; the visible dashed `--- From X ---` text is what's gone.
- **`_IngredientChip` widget**:
  - Remove `isCompact` param and its branches. Chip is always in "expanded" sizing.
  - **Width strategy (locked after lens review):** wrap the chip body in `ConstrainedBox(constraints: BoxConstraints(minWidth: 72, maxWidth: 160))`. **Do not use `IntrinsicWidth`** — `IntrinsicWidth` inside a `Wrap` forces an extra layout pass per child and bloats layout cost on larger meals (30+ ingredients). `ConstrainedBox` + `Text(maxLines: 2, overflow: ellipsis, softWrap: true)` gives the same visual result (chip hugs short content, wraps long content) without the intrinsic pass.
  - Name text: `fontSize: 14`, `fontWeight: FontWeight.w500`, color `cook.cookOnSurface` (or `cook.cookOnCompleted` when checked). `maxLines: 2`, `overflow: TextOverflow.ellipsis`.
  - Quantity text: `fontSize: 14`, `fontWeight: FontWeight.w600`, color `cook.cookAccent` (or `cook.cookOnCompleted` when checked — checked-state has strong-enough bg to drop the accent color).
  - **Remove** the per-chip source-tag pill (the small "from Dressing" sub-chip at lines 317–336). Meal-mode grouping replaces it.
  - Checked-state: `cookCompleted` bg with opaque foreground; strikethrough on the name per today's pattern for the redundancy of strike + bg swap (kitchen-light legibility wins over purist "one signal is enough").
  - Chip padding: `EdgeInsets.symmetric(horizontal: 12, vertical: 8)`. Border radius: 20 (today's value).
  - Tap target verified at Dynamic Type 2.0 — with `maxWidth: 160` and 14px text wrapping 2 lines, the chip clears 48dp height comfortably.
- **Props**: `sourceTagBuilder` callback stays (needed for grouping key); the chip itself no longer reads it.

### `app/lib/features/recipes/cook_mode/shared/widgets/active_timers_row.dart`

No changes in this epic (recipe-name prefix belongs to the multi-recipe epic).

### `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart`

File stays on disk — unreferenced after cmlp-4 deletes its call site. **Deferred deletion** (deferred-delete decision locked below). The multi-recipe epic owns removing the file + its import so the file's full lifecycle is one atomic commit.

## Backend changes

None — confirmed. No API shapes change, no persisted state shape changes, no backend calls added or removed. No mutation event shape changes. `CookSessionPersister` payload is untouched (the v1 → v2 bump belongs to the multi-recipe epic).

## Infrastructure changes

None — confirmed. No env vars, no CI workflow changes, no Terraform, no `tools/no-cook-chat-check.sh` allowlist update. Flutter-only change; `services/api` coverage gate is unaffected (no backend files touched).

## Design principles (refined)

- **Delete, don't deprecate.** Expand/Collapse, `INGREDIENTS` label, compact strip code path, `AnimatedCrossFade`, and the chip-level source tag are all removed outright. No feature flag. No silent opt-out. Tests update to assert absence.
- **Delete the render call, not the file.** The `RecipeSectionHeader` *render site* in `meal_cook_mode_screen.dart` is deleted (not commented out) because a commented-out block is worse than a clean delete: the git history already preserves the old code, and the multi-recipe epic will have to touch the surrounding `SingleChildScrollView` children list anyway. The *widget file* stays on disk until the multi-recipe epic, so the file's lifecycle (creation + deletion) lives in one clean diff-pair across two commits.
- **The group header is the source tag.** In meal mode, the user learns "this ingredient belongs to Dressing" by seeing it inside the Dressing group. Duplicating that on each chip is noise.
- **Progress bar margins align to content padding.** 24 on both for visual continuity. The current 48 feels off because it doesn't match the step card's edges.
- **Accessibility before aesthetics.** Dynamic Type wins over fixed widths. Group headers get `Semantics(header: true)`. Chip tap target stays ≥ 48dp.
- **`ConstrainedBox` over `IntrinsicWidth` inside `Wrap`.** Intrinsic passes are a known perf trap at list sizes we expect in multi-recipe meals.
- **Natural scroll over capped scroll.** The ingredient block lives in the outer `SingleChildScrollView`. No inner scroll region. Tall lists push the step card; user scrolls naturally. This is an explicit trade-off the user accepted during the 2026-04-22 session.

## File structure

Touched:
- `app/lib/features/recipes/cook_mode/cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/meal/meal_cook_mode_screen.dart`
- `app/lib/features/recipes/cook_mode/shared/widgets/ingredient_strip.dart`

Referenced but not modified:
- `app/lib/features/recipes/cook_mode/meal/widgets/recipe_section_header.dart` (call site deleted; file kept on disk until multi-recipe epic)
- `app/lib/core/theme/cook_mode_theme.dart` (consumed for tokens; not edited)

Tests modified (4) — the list from the draft is the **complete** set; grep confirms no other tests touch the removed strings/icons in cook-mode context:
- `app/test/cook_mode_test.dart` — lines 246–294: replace `find.text('Expand')` + `find.text('--- From Dressing ---')` / `--- From Salad ---` with direct expectations on the group keys (`find.byKey(Key('ingredient_group_Dressing'))`) + `find.text('Dressing')` scoped to group-header position (no Expand tap needed since the list is always expanded). Remove `findsAtLeast(1)` compact-view assertions for `'Dressing'` / `'Salad'` that were counting per-chip tag pills.
- `app/test/meal_cook_mode_ingredients_test.dart` — lines 91–171: drop the "compact: per-chip source tag visible" test entirely (compact view gone). Rewrite "expanded view" test to not tap `Expand` and to assert on `find.text('Dressing')` / `find.text('Salad')` at group-header positions plus the two `ingredient_group_*` keys. Drop the "truncate to 10 grapheme clusters" test — no chip-level tag exists to truncate. Keep the "1-component plan: no source tag chips" test but drop the `tap('Expand')` line.
- `app/test/meal_cook_mode_test.dart` — no assertion changes required by grep; add a confirmatory test `meal ingredient groups render as headers, not "--- From" dividers` scoped to a 3-recipe meal.
- `app/test/meal_cook_mode_sectioning_test.dart` — **entire `cmm-3 — recipe section header` group (lines 143–onwards) is deleted**. This test group pins the `RecipeSectionHeader` widget's componentName/localStep/componentTotal fields; with the call site removed, the widget never mounts and every `tester.widget<RecipeSectionHeader>` call fails. The file has other groups (navigator boundary rules, etc.) — they stay.
- `app/test/cook_mode_gesture_test.dart` — lines 161–192: the `IngredientStrip expand/collapse button has at least 64dp height` test must be **deleted** (no Expand button to measure). Grep confirms this is the only 48dp-or-64dp tap-target assertion on the old header.
- `app/test/cook_mode_timer_test.dart` — line 181: `find.byIcon(Icons.close)` refers to a `StepTimerChip` close button (not the cook-mode header X). **No change needed** — confirmed by reading the surrounding context (it's inside `StepTimerChip` onClose callback test). Flagged here so reviewers don't regress it.
- `app/test/cook_mode_resume_test.dart` — lines 262–272: the `overflow menu is the rightmost header icon after close` test references the cook-mode header X button (`find.byIcon(Icons.close)`) to assert overflow sits to its right. Rewrite to assert overflow sits right of the cooking-time badge (`find.byIcon(Icons.schedule)`) instead — the X is gone so the comparison's left-hand side moves one slot left.

## Stories

### cmlp-1 — Remove X button from cook-mode header (both modes)

**Changes**
- `cook_mode_screen.dart` — delete the `IconButton` block at lines 1057–1062 (the one with `Icons.close` and `_exitCookMode`). Update header outer `padding` on line 975 to `EdgeInsets.fromLTRB(8, 4, 12, 4)`.
- `meal_cook_mode_screen.dart` — delete the mirror `IconButton` at line 1237. Same padding tweak on its header container.

**Acceptance criteria**
- `find.byIcon(Icons.close)` in a cook-mode header subtree returns nothing (both recipe + meal mode).
- Back button (`Icons.arrow_back`) is the sole exit affordance. Overflow menu's Reset-cook still works.
- `cook_mode_resume_test.dart`'s `overflow menu is the rightmost header icon` test is rewritten to compare `Icons.more_vert` right-edge vs. `Icons.schedule` right-edge.
- No other test file regresses (grep on `Icons.close` in cook-mode context returns only the `StepTimerChip` callback test in `cook_mode_timer_test.dart`, which is unrelated).

### cmlp-2 — Ingredient strip: drop header + Expand/Collapse + compact strip + empty guard

**Changes** (`ingredient_strip.dart`)
- Delete `_isExpanded` state (line 38), the header `Padding` block (lines 52–105), the `AnimatedCrossFade` (lines 108–115), `_buildHorizontalStrip` (lines 121–144), and the `isCompact` branch inside `_IngredientChip` (lines 268–345).
- Add `if (widget.ingredients.isEmpty) return const SizedBox.shrink();` at the top of `build()`.
- Refactor `build()` to return the expanded layout directly (no `AnimatedContainer` / `AnimatedCrossFade` wrapper).

**Acceptance criteria**
- `find.text('INGREDIENTS')`, `find.text('Expand')`, `find.text('Collapse')` all return `findsNothing` anywhere in cook-mode tests.
- `find.byType(AnimatedCrossFade)` inside the cook-mode subtree returns `findsNothing`.
- New test in `cook_mode_test.dart`: mount `IngredientStrip(ingredients: const [], checkedIndices: const {}, onToggle: (_) {})` and assert `find.byType(Padding)` inside it returns `findsNothing` and the rendered size is zero.
- Updated tests: `cook_mode_test.dart:246–294`, `meal_cook_mode_ingredients_test.dart:91–171`, `cook_mode_gesture_test.dart:161–192` (deleted).
- Ingredient list is visible on initial mount without any tap.

### cmlp-3 — Ingredient chip readability pass

**Changes** (`_IngredientChip` in `ingredient_strip.dart`)
- Remove `isCompact` param and the `sourceTag` param (both dead after cmlp-2).
- Wrap chip body in `ConstrainedBox(constraints: BoxConstraints(minWidth: 72, maxWidth: 160))`.
- Name `Text` styled `fontSize: 14, fontWeight: w500, color: cookOnSurface` (or `cookOnCompleted` when checked), `maxLines: 2, overflow: ellipsis`.
- Quantity `Text` styled `fontSize: 14, fontWeight: w600, color: cookAccent` (or `cookOnCompleted` when checked).
- Chip padding `EdgeInsets.symmetric(horizontal: 12, vertical: 8)`, border radius 20.

**Acceptance criteria**
- At `MediaQuery(textScaler: TextScaler.linear(1.3))` and `TextScaler.linear(2.0)`, chip content does not clip (no `RenderFlex overflowed` warnings in a widget test that wraps `IngredientStrip` with a long-named ingredient like `"Freshly ground black peppercorns"`).
- Quantity is rendered with `cookAccent` color at 14px w600 in an unchecked chip (golden-free contrast assertion: read the `Text`'s `TextStyle` via `tester.widget<Text>`).
- `IntrinsicWidth` is NOT used anywhere in the refactored chip tree (`find.byType(IntrinsicWidth)` inside strip returns `findsNothing`).
- No source-tag pill visible anywhere (`find.textContaining('from ', findRichText: true)` returns `findsNothing` within the chip tree).
- Manual visual check in light + dark + system themes — no golden baseline exists, so dogfood verification only; documented in story QA notes.

### cmlp-4 — Meal mode: group headers + delete section header above step card

**Changes** (`ingredient_strip.dart` meal branch + `meal_cook_mode_screen.dart`)
- In `_buildExpandedGrid` meal branch, replace `--- From $rawTag ---` dashed-text dividers with group-header widget: `Padding(fromLTRB(16, 16, 16, 4), child: Semantics(header: true, child: Column([Text(name, 13px w600 letterSpacing 0.4 color cookOnSurface.alpha(0.7)), SizedBox(4), Divider(height: 1, color: cookDivider.alpha(0.5))])))`.
- Preserve `Key('ingredient_group_$rawTag')` and `Key('ingredient_group_untagged')` on the outer group containers.
- Untagged group reads `Other`; only rendered if the untagged set is non-empty.
- In `meal_cook_mode_screen.dart`, **delete** lines 1350 (the `showSectionHeader` local) and 1357–1364 (the `if (showSectionHeader) ... RecipeSectionHeader(...) SizedBox(height: 8)` block). The import of `RecipeSectionHeader` becomes unused — **remove the import** as well.

**Acceptance criteria**
- Meal cook mode shows `Dressing`, `Salad`, `Grilled Chicken` as standalone group headers in the ingredient list — asserted by `find.text('Dressing')`, `find.text('Salad')`, `find.text('Grilled Chicken')` each `findsOneWidget` in the ingredient subtree (keys: `ingredient_group_*`).
- `find.textContaining('--- From ')` returns `findsNothing` across all cook-mode tests.
- `meal_cook_mode_sectioning_test.dart`'s `cmm-3 — recipe section header` group is deleted (it would otherwise fail compilation — the widget never mounts).
- `find.byType(RecipeSectionHeader)` returns `findsNothing` in meal mode.
- `"Dressing · 1 / 7"` string appears nowhere (the `· N / M` section-header format is gone).
- Each group-header node carries `Semantics(header: true)` — verified with `tester.getSemantics(find.text('Dressing')).hasFlag(SemanticsFlag.isHeader)`.
- The `RecipeSectionHeader` widget file `recipe_section_header.dart` is **not** deleted (explicit check: `File('.../recipe_section_header.dart').existsSync()` in a repo-integrity smoke — or just a reviewer note).

### cmlp-5 — Progress bar + header padding polish

**Changes**
- `cook_mode_screen.dart:1119` and `meal_cook_mode_screen.dart:1369`: `horizontal: 48` → `horizontal: 24`.
- Header outer padding tweaks already covered in cmlp-1; this story is the visual QA gate that confirms nothing double-padded.

**Acceptance criteria**
- Progress bar's outer `Container.margin` is `EdgeInsets.symmetric(horizontal: 24)` in both cook-mode screens — asserted by `tester.widget<Container>(find.ancestor(of: find.byType(LinearProgressIndicator), matching: find.byType(Container)).first).margin == EdgeInsets.symmetric(horizontal: 24)`.
- Header doesn't visually collide with cooking-time badge after X-button removal (manual dogfood check on iPhone 13 + Pixel 6 + iPad mini size classes; no test pins the 48dp value after this change — confirmed by grep that no test asserts `horizontal: 48` or `48.0` in cook-mode context).
- Top-of-screen chrome (header + active-timers row + ingredient list top) has no double-padded gap at the join.

## Dependencies

- **Blocks** `epic-cook-mode-multi-recipe-flow` — the multi-recipe epic assumes this epic's ingredient-strip refactor, the section-header removal, and the chip typography tokens have landed.
- **Depends on** `epic-cook-mode-meal` (shipped; extracted shared widgets under `cook_mode/shared/` are the editing surface).
- **Depends on** `epic-cook-mode-polish` (shipped; `CookModeTheme` tokens `cookAccent`, `cookCompleted`, `cookOnCompleted`, `cookSurfaceDim`, `cookDivider`, `cookOnSurface` are the styling surface).

## Open questions for the user

None. All visual decisions for this epic are locked by the 2026-04-22 planning session (see PRD addendum) and the 2026-04-22 party-mode refinement captured above. Deferrals live explicitly in the next epic's scope (see below).

## Locked decisions propagating to epic-cook-mode-multi-recipe-flow

The following decisions are **inherited as-is** by the multi-recipe-flow epic's party-mode. The next epic should not re-open these:

1. **Chip typography tokens.** Name `14px w500 cookOnSurface / cookOnCompleted`. Quantity `14px w600 cookAccent / cookOnCompleted`. Padding `(12, 8)`. Radius `20`. If the toggle bar epic needs a different chip variant (e.g., for active-recipe highlight), it wraps these tokens rather than redefining them.
2. **Chip width strategy.** `ConstrainedBox(minWidth: 72, maxWidth: 160)` — not `IntrinsicWidth`. Any new chip-like surface (toggle-bar pill) follows the same constraint pattern.
3. **Ingredient block scroll behavior.** No internal scroll region. Lives in the outer `SingleChildScrollView`. If the multi-recipe toggle bar wants to pin itself, it does so via the outer column's layout, not via a nested ingredient scroll viewport.
4. **Group-header shape (meal mode).** `13px w600 letterSpacing 0.4 cookOnSurface.alpha(0.7)` + 1dp `cookDivider.alpha(0.5)` divider + 4dp spacer, `Semantics(header: true)`. The toggle-bar epic reuses this shape for any future section-like chrome.
5. **Section-header-file lifecycle.** `recipe_section_header.dart` is **orphaned on disk** after this epic (no imports, no render site). The multi-recipe epic's first story deletes the file and removes any final dangling references as part of its own refactor. Do not delete it earlier — the lifecycle is one atomic commit in the next epic.
6. **Empty-ingredient behavior.** `IngredientStrip` returns `SizedBox.shrink()` when `ingredients.isEmpty`. The multi-recipe toggle bar should adopt the same "render nothing when empty" posture for any per-recipe chrome (e.g., a 1-component meal renders no toggle bar at all).
