<!-- refined via party-mode 2026-04-18 -->
<!-- 2026-04-18 UPDATE: POST /v1/shopping-lists/{id}/populate-from-calendar was removed by epic-calendar-per-meal-shopping-add (FR-CPMS-1/FR-CPMS-7). Story mcal-4 is `deleted` in sprint-status.yaml. Impact on this epic: (a) any reference to "PopulateFromCalendar" below is stale; (b) End-User Flow primary-path step 7 ("Add to Shopping List on the detail sheet calls PopulateFromCalendar with include_meal_event_ids=[this_event_id]") needs a new transport at implementation time — recommended: a new `POST /v1/meal-events/{event_id}/add-to-shopping-list` thin endpoint mirroring the per-Meal `POST /v1/meals/{meal_id}/add-to-shopping-list` (mcal-5) with the same `aggregate_meal_ingredients` dedupe for Meal events and a simple `populate_from_recipe` call for Recipe events. Revisit when this epic is unfrozen. FR-MEAL-12 (sum-within-meal dedupe) is NOT retracted, only its transport path changes. -->
# Epic: Meals — Calendar Integration (plan-meal sheet, meal events, recurrence, shopping list)

## Overview

`epic-meals-create-and-view` (foundation) shipped the Meal entity, its book-scoped UI, and the Meal detail screen whose action bar has **disabled-with-tooltip** slots for Plan-for-Date and Add-to-Shopping-List. `epic-meals-discoverability` (landed) surfaced Meals on home, search, favorites, and recipe detail. **This epic is where Meal meets Calendar.** The plan-meal sheet gets a Recipe/Meal segmented control; `meal_events.meal_id` and `meal_recurrence_rules.meal_id` columns land with a `num_nonnulls(recipe_id, meal_id) <= 1` check constraint; the calendar grid + day sheet render Meal events with a "N recipes" cue; and `PopulateFromCalendar` expands a Meal event into its component recipes' ingredients with **sum-within-meal dedupe** (1 tbsp + 1 tbsp olive oil across components → 2 tbsp on the shopping list).

This is the biggest cross-layer integration of the four Meals epics. The load-bearing correctness bar: **any single-recipe meal_event must behave pixel- and byte-identically to today**. Regression fixtures below codify this.

**Goal.** When this epic ships, Leo opens Calendar → taps Tuesday dinner → the plan-meal sheet has a **Recipe / Meal** `SegmentedButton` at the top of the picker row. He toggles to Meal, searches "Kale Salad Meal," picks it, saves. Tuesday's dinner slot renders **"Kale Salad Meal"** with a stack icon + muted "2 recipes" caption. Tapping the event opens the calendar's meal-event detail sheet — now with an **Open Meal** row (push `/meals/:id`) and an **Open Recipe** action that opens a tiny "Which recipe?" bottom-sheet chooser when the event has 2+ components. Tapping **Add to Shopping List** calls `PopulateFromCalendar` for that event's slot; both Kale Salad and Lemon Dressing ingredients land on the list, with overlapping olive oil merged to 2 tbsp. Repeating the meal every Monday uses the same plan-meal sheet's Repeats picker; Profile → Recurring Plans renders it as "Every Monday dinner · Kale Salad Meal (2 recipes)".

**Foundation action-bar contract honored.** Foundation's Meal detail action bar has six slots: Favorite (live), **Plan for Date** (wired live in THIS epic — launches plan-meal sheet pre-filled to Meal mode with the current Meal), **Add to Shopping List** (wired live in THIS epic — see "Shop without scheduling" below), Share (still disabled — ships with sharing epic), Archive, Edit. Slot positions do not move; we are filling in contracts foundation already drew.

**Shop without scheduling.** A user who wants to buy a Meal's ingredients without putting it on the calendar needs a code path. This epic adds a thin `POST /v1/meals/{meal_id}/add-to-shopping-list` handler that accepts a target `shopping_list_id`, expands components via the same `aggregate_meal_ingredients` service that `PopulateFromCalendar` uses, and appends the summed rows with `meal_event_id=NULL` and a new `source_meal_id` column on `shopping_list_items`. This makes the Meal-detail "Add to Shopping List" action live in v1 — the foundation slot stops being a placeholder.

**Scope boundary.** No changes to sharing, MCP, AI pairing, the participant model, recurrence grammar, or the calendar-foundation authorization path. The `meals.share_token` column exists but still no endpoint reads it. No new env vars, no new AWS resources.

## End-User Flow

### Primary path — scheduling a Meal

1. Leo opens Calendar. The header still shows the active Calendar (unchanged from `epic-calendars-foundation`).
2. He taps Tuesday → plan-meal sheet opens. At the top of the picker row, a **`SegmentedButton` with two segments: Recipe | Meal**. Default: **Recipe** (see Principle 2). If Leo launched the sheet via "Plan for Date" from the Meal detail screen, the sheet opens with Meal selected and the Meal pre-filled. Other entry points (calendar FAB, day-tap, recipe detail "Plan for…") default to Recipe.
3. He toggles to Meal → `RecipeAutocompleteField` is replaced by `MealAutocompleteField`, which debounces at 300ms and queries `GET /v1/meals?q=<text>&limit=8` (see Backend Changes). He types "Kale," sees **"Kale Salad Meal (2 recipes)"** from his "Dinners" book, and taps it.
4. He sets meal-type to Dinner, leaves date on Tuesday, saves. Sheet dismisses. Toast: "Kale Salad Meal added to calendar."
5. Tuesday evening slot now renders **"Kale Salad Meal"** as the primary label + small `Icons.layers` stack icon + muted "2 recipes" caption. Single-recipe events render unchanged.
6. He taps the event → meal-event detail sheet. New rows:
   - **Open Meal** — visible only when `meal_id` set. Pushes `/meals/:id`.
   - **Open Recipe** — when event has 2+ components, tapping opens `CalendarRecipeChooserSheet` (small bottom sheet, title "Which recipe?", list of component recipes, tap → `/recipes/:id`). When event has exactly 1 available component (because others were archived), taps skip the chooser and push directly.
   - Existing Reschedule / Unschedule / Mark as Cooked — unchanged visually, semantic update below.
7. **Add to Shopping List** on the detail sheet calls `PopulateFromCalendar` with `include_meal_event_ids=[this_event_id]`. The response summarizes `items_added` / `items_skipped` — snackbar reads "Added N items from Kale Salad Meal."

### Recurring Meal

8. Leo opens the plan-meal sheet's Repeats picker, sets "Every Monday dinner," saves. A `meal_recurrence_rule` is created with `meal_id` set and `recipe_id` null. The rolling-window materializer expands it; each Monday's dinner slot shows "Kale Salad Meal (2 recipes)" + the existing recurring badge.
9. From Profile → Recurring Plans, the rule row renders **"Every Monday dinner · Kale Salad Meal (2 recipes)"**. Tap-to-edit opens the plan-meal sheet in Meal mode with the Meal pre-filled. End-Series-Today works unchanged.

### Mark-as-Cooked on a Meal event (resolved decision)

10. Leo taps **Mark as Cooked** on a Monday Meal event. One Meal-level `CookingLog` row is created with `meal_id` set, `recipe_id` NULL, and `cooked_at=now`. Per-component fan-out rows are created for each component with `recipe_id` set + **`parent_meal_log_id` FK** pointing at the Meal-level log. The recipe detail screen's "last cooked" display continues to count component-level rows (cook-history accuracy preserved). The Meal detail screen (future epic) will display "Cooked the Kale Salad Meal on 4/17" from the Meal-level row. One user action, both views stay correct. **DB migration**: `cooking_logs.recipe_id` becomes nullable; add `meal_id` nullable FK; add `parent_meal_log_id` nullable self-FK; add check constraint `ck_cooking_logs_target_xor` = `num_nonnulls(recipe_id, meal_id) = 1` **unless `parent_meal_log_id` is set** — parent rows are Meal-level (meal_id only), fan-out children are recipe-level (recipe_id only, parent_meal_log_id set).

### Shop without scheduling (from Meal detail)

11. Leo opens Kale Salad Meal detail (no event scheduled). Tapping **Add to Shopping List** shows a shopping-list picker (reuses the one from recipe detail → `PopulateFromRecipe` flow), he picks "Groceries," and the Meal expands via the same `aggregate_meal_ingredients` service. Items land with `meal_event_id=NULL` + `source_meal_id=<meal_id>`. Same sum-within-meal dedupe. Snackbar: "Added N items from Kale Salad Meal."

### What does not change

Single-recipe meal_event behavior (zero regression — see QA regression fixture below). Day-detail-sheet layout. `meal_event_participants` semantics (still attached to events, not components). Recurrence grammar (weekly/biweekly/monthly-nth-weekday). Calendar switcher/create/delete. Per-event per-day shopping-list separation (Monday Meal + Wednesday same Meal → two separate groups of items).

## Frontend Changes

Touches `app/lib/features/calendar/` heavily; `app/lib/features/meals/` lightly (action-bar wiring); `app/lib/features/profile/recurring_plans/` lightly.

### Control choice: `SegmentedButton` (Material 3) — decided

The app is Material-first (`MaterialApp`, `ThemeData.useMaterial3: true` in `app/lib/core/theme/theme.dart`). `CupertinoSegmentedControl` would be a stylistic outlier. `SegmentedButton<PlanMealType>` with two entries (Recipe / Meal) sits cleanly above the autocomplete; the existing `GestureDetector`-based meal-type chip row in `plan_meal_sheet.dart` is a good precedent for the M3 chip-button look but a `SegmentedButton` carries the Material 3 "segmented control" semantics the user already sees in recurrence-interval pickers elsewhere.

### Plan-meal sheet layout fit (UX audit)

Today's sheet on small screens (iPhone SE-class, 568pt height): Header + name field + calendar row (conditional) + date row + meal-type chips + Repeats + Save = ~540pt. Adding a `SegmentedButton` row (~48pt) pushes to ~590pt. On SE we'd scroll. **Fix**: wrap the body in a `SingleChildScrollView` (it isn't one today) at sheet open. This is a small, isolated change bounded to `plan_meal_sheet.dart`. No other layout changes.

### Default-state sharpening (PM lens)

- **Entry from calendar FAB / day-tap / recipe detail "Plan for…"**: Recipe mode selected. `mealId` unset. (Existing muscle memory; zero-regression for users with no Meals.)
- **Entry from Meal detail "Plan for Date" action**: Meal mode selected; the Meal is pre-filled in `MealAutocompleteField` with `Linked to <MealName>` chip (parallel to the existing recipe-link chip).
- **Edit mode on an existing meal_event**: whichever mode the event already is (Recipe vs. Meal). The toggle is still visible but switching it clears the other side's linkage — same ergonomics as detaching a linked recipe today.

### File list

- **`widgets/plan_meal_sheet.dart`** (MODIFY)
  - Add `SegmentedButton<PlanMealType>` at the top of the picker row (above `RecipeAutocompleteField`/`MealAutocompleteField`).
  - Wrap body in `SingleChildScrollView` so small screens fit without clipping.
  - Add `_selectedPlanMealType` state; default resolved from caller (`widget.initialPlanMealType` if passed, else Recipe).
  - New `widget.initialMealId` + `widget.initialMealName` props for Meal-detail launch.
  - `_save()` branches: Recipe path unchanged; Meal path calls `createMealEvent(..., mealId: pickedMealId)` or `createRecurrenceRule(..., mealId: pickedMealId)` (never both `recipeId` and `mealId`).
- **`widgets/meal_autocomplete_field.dart`** (NEW) — parallels `recipe_autocomplete_field.dart`. Debounced 300ms. Calls `GET /v1/meals?q=...&limit=8`. `PickedMeal` result shape carries `mealId`, `name`, `componentCount`, collage thumbs. Linked-chip "Linked to <MealName>" + detach affordance (detach switches back to free-text-name mode, but Meal-mode always requires a picked meal — so detach clears the name entirely and disables Save until re-pick).
- **`features/calendar/widgets/calendar_event_tile.dart`** (MODIFY if standalone widget exists, else inline where `calendar_screen.dart` renders the grid tile): when `event.mealId != null`, render "MealName" + `Icons.layers` + muted `<N> recipes` caption. When `event.recipeId != null`, render as today. Shared constant `kMealComponentCountLabel(int n) => '$n recipes'` exported from `app/lib/features/meals/widgets/meal_tile.dart` (foundation already owns the badge text format) — calendar imports the helper so the two surfaces never drift.
- **`widgets/day_detail_sheet.dart`** (MODIFY) — same rendering branch.
- **`widgets/meal_event_detail_sheet.dart`** (MODIFY) — add **Open Meal** row (visible when `mealId` set). Modify **Open Recipe** action: if event has 1 available component, push directly; if ≥2, open `CalendarRecipeChooserSheet`.
- **`widgets/calendar_recipe_chooser_sheet.dart`** (NEW) — bottom sheet. Title: **"Which recipe?"** (decided — terse, matches iOS convention, matches recipe-chooser patterns elsewhere in app). Vertical list of available component recipes: thumbnail + name + book subtitle. Unavailable components are **omitted entirely** (not shown-and-disabled) so the user isn't offered a dead link.
- **Choice: bottom sheet, not full screen** — matches the existing detail-sheet modal stack pattern, avoids push-transition jank when the user is 2 sheets deep, and carries natural dismiss affordance.
- **`widgets/recurrence_field.dart`** (MODIFY, minimal) — no UI change. The picker just passes the current Recipe/Meal mode state through to rule-create; the server does the work.
- **`services/meal_calendar_service.dart`** (MODIFY) — `createMealEvent` + `updateMealEvent` + `createRecurrenceRule` accept `mealId?` (XOR with `recipeId?`). Client-side assertion rejects both-set before the network call (so a misuse surfaces in tests, not at prod).
- **`features/calendar/models/meal_event.dart`** (MODIFY) — add `mealId?`, `mealSummary?: MealSummary` fields. `MealSummary`: id, name, componentCount, top 4 component image URLs.
- **`features/meals/meal_detail_screen.dart`** (MODIFY) — wire the two foundation placeholder slots:
  - **Plan for Date** action: launches `PlanMealSheet` with `initialPlanMealType: PlanMealType.meal, initialMealId: meal.id, initialMealName: meal.name`. Tooltip removed; action becomes enabled.
  - **Add to Shopping List** action: launches the existing shopping-list picker; on pick, calls `MealService.addToShoppingList(mealId, shoppingListId)`. Tooltip removed; action becomes enabled.
- **`features/meals/services/meal_service.dart`** (MODIFY) — add `addToShoppingList(mealId, shoppingListId)` hitting the new endpoint; add `searchMeals(query, {int limit = 8})` hitting `GET /v1/meals?q=...&limit=...`.
- **`features/profile/recurring_plans/recurring_plans_screen.dart`** (MODIFY) — render Meal rules as "Every X · MealName (N recipes)". Tap-to-edit opens the plan-meal sheet in Meal mode pre-filled.

### Widget tests (non-negotiable)

- `plan_meal_sheet_meal_mode_test.dart`:
  - SegmentedButton renders Recipe/Meal; default state matches caller context (calendar FAB → Recipe; Meal-detail entry → Meal with pre-fill).
  - Toggling to Meal swaps autocomplete to `MealAutocompleteField`.
  - Save with Meal mode dispatches `createMealEvent(mealId: ..., recipeId: null)`.
  - XOR client assertion: passing both `recipeId` and `mealId` throws `AssertionError` in debug mode (no network call).
  - Small-screen layout: `find.byType(SingleChildScrollView)` is present; SE-sized fixture does not clip the Save button.
- `meal_autocomplete_field_test.dart`:
  - 300ms debounce; network call fires after timer.
  - Results render with "N recipes" badge.
  - Detach clears the picked mealId.
- `calendar_event_tile_meal_test.dart`:
  - `event.mealId` set → renders MealName + "2 recipes" caption + stack icon.
  - `event.recipeId` set → renders as today (regression fixture).
  - Caption copy uses the shared `kMealComponentCountLabel` helper.
- `meal_event_detail_sheet_test.dart`:
  - Open Meal row visible iff `mealId` set.
  - Open Recipe → chooser appears when 2+ components, pushes directly when 1.
  - Chooser omits unavailable components.
- `calendar_recipe_chooser_sheet_test.dart`:
  - Title text: "Which recipe?"
  - Tapping a row pushes `/recipes/:id` and pops the chooser.
- `meal_detail_plan_shop_actions_test.dart`:
  - Plan-for-Date action launches PlanMealSheet in Meal mode.
  - Add-to-Shopping-List action launches shopping-list picker, then hits `addToShoppingList` endpoint.
- `recurring_plans_screen_meal_test.dart`:
  - Meal rule renders with "N recipes" suffix.
  - Tap opens plan-meal sheet in Meal mode pre-filled.

## Backend Changes

### Models

- **`libraries/utils/utils/models/meal_event.py`** (MODIFY) — add:
  ```python
  meal_id: Mapped[uuid.UUID | None] = mapped_column(
      UUID(as_uuid=True),
      ForeignKey("meals.id", ondelete="SET NULL"),
      nullable=True,
  )
  meal: Mapped["Meal | None"] = relationship()
  ```
  Add `CheckConstraint("num_nonnulls(recipe_id, meal_id) <= 1", name="ck_meal_events_recipe_xor_meal")` — naming pattern parallels existing `uq_meal_events_rule_scheduled_at`. Add `Index("ix_meal_events_meal_id", "meal_id")`.
- **`libraries/utils/utils/models/meal_recurrence_rule.py`** (MODIFY) — parallel treatment. Constraint name `ck_meal_recurrence_rules_recipe_xor_meal`. Index `ix_meal_recurrence_rules_meal_id`.
- **`libraries/utils/utils/models/cooking_log.py`** (MODIFY) — add `meal_id` nullable FK, `parent_meal_log_id` nullable self-FK, drop not-null from `recipe_id`. Check constraint: `ck_cooking_logs_target` = `(num_nonnulls(recipe_id, meal_id) = 1) OR (parent_meal_log_id IS NOT NULL AND recipe_id IS NOT NULL AND meal_id IS NULL)`. The second clause covers fan-out child rows.
- **`libraries/utils/utils/models/shopping_list_item.py`** (MODIFY) — add `source_meal_id` nullable FK to `meals.id` ondelete SET NULL. No check constraint with `recipe_id` / `meal_event_id` — a shopping-list item can legitimately have all three (derived from a Meal event that came from a recipe inside that Meal). Column is purely descriptive: "I came from this Meal's aggregate."

### Migration

**`services/migrator/migrations/versions/<yyyymmddhhmm>_add_meal_id_to_calendar_and_cooking_logs.py`** (NEW). One alembic revision covering:

1. `meal_events.meal_id` nullable FK + `ix_meal_events_meal_id` + check constraint `ck_meal_events_recipe_xor_meal` created `NOT VALID` then `VALIDATE CONSTRAINT` as a second statement.
2. `meal_recurrence_rules.meal_id` nullable FK + `ix_meal_recurrence_rules_meal_id` + check constraint `ck_meal_recurrence_rules_recipe_xor_meal`, same NOT VALID pattern.
3. `cooking_logs`: drop NOT NULL from `recipe_id`; add `meal_id` nullable FK + `parent_meal_log_id` nullable self-FK; add check constraint `ck_cooking_logs_target` (the two-clause version from Models § above), NOT VALID + VALIDATE.
4. `shopping_list_items.source_meal_id` nullable FK. No constraint — additive.

**Migration safety confirmed**. `NOT VALID` on a new check constraint does NOT rewrite existing rows; it only applies to new INSERTs/UPDATEs. `VALIDATE CONSTRAINT` then scans existing rows but does NOT take an ACCESS EXCLUSIVE lock on the table — it's SHARE UPDATE EXCLUSIVE, which allows concurrent reads + writes. Safe on prod-sized `meal_events` (which today holds O(10k) rows at our scale; even at 10M rows the validate scan completes in minutes).

**`down_revision`** points at the most recent migration in `services/migrator/migrations/versions/` — **explicitly NOT the foundation migration**. Alembic's linear revision chain already enforces "foundation migration applies first." Documenting it here so sprint order is unambiguous: foundation's `<ts>_add_meals_and_meal_recipes_and_meal_favorites.py` is a prerequisite; this migration will fail if the `meals` table doesn't exist (the FK references it).

**`downgrade()`** reverses cleanly: drops the new columns, constraints, indexes, and restores `cooking_logs.recipe_id` NOT NULL (only safe if no Meal-level log rows exist; downgrade asserts `SELECT COUNT(*) FROM cooking_logs WHERE recipe_id IS NULL = 0` and raises if not).

### Schemas

- **`services/api/src/schemas/meal_event.py`** (MODIFY):
  - `CreateMealEventRequest` / `UpdateMealEventRequest` gain optional `meal_id: UUID | None = None`. Pydantic `model_validator(mode="after")` rejects both-set with 422 code `MEAL_EVENT_RECIPE_XOR_MEAL`.
  - `MealEventResponse` gains optional `meal_summary: MealSummary | None = None` — populated when `meal_id` set. Old clients parsing the response see an additive key; no removal, no rename.
- **`services/api/src/schemas/recurrence_rule.py`** (MODIFY) — parallel.
- **`services/api/src/schemas/shopping_list_item.py`** (MODIFY) — response adds `source_meal_id` nullable.

### Handlers

- **`services/api/src/api/v1/meal_event/create_meal_event.py`** (MODIFY) — validate XOR; if `meal_id` supplied, `SELECT ... FROM meals WHERE id=:meal_id AND archived_at IS NULL`, 404 if missing; verify the user has **read membership** on the Meal's `recipe_book_id` via `require_book_read_access` (reuses foundation's dependency); store `meal_id`, leave `recipe_id` null. Title: when `meal_id` set, default to `meal.name` at create time (matches how recipe title flows today via `_resolve_title` semantics).
- **`services/api/src/api/v1/meal_event/update_meal_event.py`** (MODIFY) — support mode-switching (caller sets the new FK, server clears the other).
- **`services/api/src/api/v1/meal_event/list_meal_events.py`** (MODIFY) — `selectinload(MealEvent.meal).selectinload(Meal.components).selectinload(MealRecipe.recipe)`. Hydrate `meal_summary` (id, name, component_count, top-4 component image URLs) when `meal_id` present. Recipe hydration path (when `recipe_id` present) unchanged.
- **`services/api/src/api/v1/meal_event/get_meal_event.py`** (MODIFY) — parallel hydration.
- **`services/api/src/api/v1/recurrence_rule/create_recurrence_rule.py`** / `update_recurrence_rule.py` / `list_recurrence_rules.py` / `get_recurrence_rule.py` (MODIFY) — parallel treatment.
- **`services/api/src/api/v1/meals/list_meals.py`** (MODIFY — from foundation + discoverability) — add `?q=<search>` + `?limit=<n>` query params for the Meal autocomplete. Predicate: `name ILIKE '%q%'` OR `description ILIKE '%q%'`, scoped to books user can read, excludes archived. Reuses the existing `selectinload` hydration. (Why not use `/v1/search?scope=meals` — that endpoint returns a full sectioned response shape; the autocomplete wants a flat list. Keep autocomplete thin.)
- **`services/api/src/api/v1/shopping_list/populate_from_calendar.py`** (MODIFY — LOAD-BEARING) — see detailed spec below.
- **`services/api/src/api/v1/meals/add_meal_to_shopping_list.py`** (NEW) — `POST /v1/meals/{meal_id}/add-to-shopping-list`, body `{shopping_list_id: UUID}`. Verifies read access on Meal + write access on shopping list. Calls `aggregate_meal_ingredients(meal_id)`; inserts `ShoppingListItem` rows with `meal_event_id=NULL`, `source_meal_id=meal_id`, `recipe_id` from the component, `added_by_user_id=user.id`. Uses the same sum-within-meal dedupe. Response: `{items_added, items, meal_summary}`.
- **`services/api/src/api/v1/cooking_log/create_cooking_log.py`** (MODIFY — or new handler if create lives elsewhere) — accept optional `meal_event_id`. When event has `meal_id`: create one parent Meal-level row (`meal_id` set, `recipe_id` NULL) + one child recipe-level row per component (`recipe_id` set, `parent_meal_log_id` = parent.id). When event has `recipe_id`: existing single-row path.

### Service: `aggregate_meal_ingredients` (the centerpiece)

New in `libraries/utils/utils/services/meal_service.py`:

```python
def aggregate_meal_ingredients(
    meal: Meal,
    session: Session,
) -> list[AggregatedIngredient]:
    """Expand a Meal into a list of summed-and-deduped ingredients.

    Loads every component recipe's ingredients, normalizes each ingredient's
    unit via `normalize_unit_display` (unit_aliases table is live as of
    riip-1), and sums quantities on the dedupe key
    `(ingredient_id, normalized_unit)`.

    Components whose recipe is archived OR whose book the user cannot read
    are skipped with a warning log (not an error).

    Returns a list of AggregatedIngredient: (ingredient_id, ingredient_name,
    category, summed_quantity, normalized_unit, contributing_recipe_ids).
    """
```

**Dedupe key**: `(ingredient_id, normalized_unit)`. The `unit_aliases` table **is live** (verified — `libraries/utils/utils/services/units/normalize.py` ships `normalize_unit_display`; `services/migrator/migrations/versions/20260418040000_create_unit_aliases.py` created the table). **No fallback needed.** If `normalize_unit_display` returns a miss (aliases cache doesn't know the unit), the function returns the trimmed/lowered/punctuation-stripped input — which gives us the same stable key for "Tbsp" and "tbsp." across recipes. The fallback path documented in the draft (`LOWER(TRIM(unit))`) is **not needed** at ship time; leaving as a note in case the table is ever rolled back.

**Edge cases the implementation must handle**:
- Two components, same ingredient, same canonical unit → **one line, summed quantity**.
- Two components, same ingredient, **different units** ("1 tbsp olive oil" + "15 ml olive oil") → **two separate lines** in v1. Cross-unit conversion is out of scope; the user sees both lines and can reconcile. Note this in the UI's post-add snackbar wording if tests expose the pattern.
- Ingredient with `null` unit ("2 eggs") → dedupe key `(ingredient_id, None)`, treated as a distinct key from any unit-specified variant. Consistent with how `PopulateFromCalendar` handles it today.
- Component has zero ingredients (recipe has no ingredient rows) → skip component cleanly; log debug.

### `PopulateFromCalendar` modification (load-bearing regression bar)

**`services/api/src/api/v1/shopping_list/populate_from_calendar.py`** — the per-event loop at today's lines 134–204 gains a branch. Pseudocode:

```python
for meal_event in meal_events:
    if meal_event.meal_id is not None:
        # Expand Meal → per-(ingredient, normalized_unit) summed rows.
        aggregates = aggregate_meal_ingredients(meal_event.meal, session=self.db)
        for agg in aggregates:
            key = (agg.ingredient_id, meal_event.id)
            if key in existing_items:
                items_skipped += 1
                continue
            # Pantry-check parity: if check_pantry && pantry has this ingredient,
            # reduce needed_quantity by pantry_qty; if pantry meets demand, skip.
            ...
            item = ShoppingListItem(
                shopping_list_id=shopping_list.id,
                name=agg.ingredient_name,
                quantity=agg.summed_quantity,
                unit=agg.normalized_unit,
                category=agg.category,
                ingredient_id=agg.ingredient_id,
                recipe_id=None,  # multi-recipe origin — null the single-recipe FK
                meal_event_id=meal_event.id,
                source_meal_id=meal_event.meal_id,  # new column
                already_have_quantity=already_have,
                added_by_user_id=user.id,
            )
            ...
    elif meal_event.recipe is not None:
        # Existing recipe-only path — IDENTICAL to today, byte-for-byte.
        ...
    else:
        # meal_id null AND recipe_id null — free-text event, skip as today.
        continue
```

**The existing recipe branch is not modified.** The new code is a sibling branch, not a refactor of the old. This is the regression bar: recipe-only events produce the exact same `ShoppingListItem` rows as before.

**Selectinload extension**: the top-level query eager-loads `MealEvent.meal → Meal.components → MealRecipe.recipe → Recipe.ingredients → RecipeIngredient.ingredient` via chained `selectinload`. Two extra queries regardless of how many events or components — the batched IN pattern.

### Rolling-window recurrence materializer audit (`libraries/utils/utils/recurrence/materializer.py`)

**Audit finding**: the current `_resolve_title` at line 137 falls back to `rule.title or "Meal"` when `rule.recipe_id` is null. For Meal rules we need title to be `meal.name`. Extension:

```python
def _resolve_title(rule: MealRecurrenceRule, db: Session) -> str:
    if rule.meal_id is not None:
        meal = db.query(Meal).filter(Meal.id == rule.meal_id).first()
        if meal is not None:
            return meal.name
    if rule.recipe_id is not None:
        recipe = db.query(Recipe).filter(Recipe.id == rule.recipe_id).first()
        if recipe is not None:
            return recipe.name
    return rule.title or "Meal"
```

**Insert pass extension** (line 200–219): the `insert_values` dict needs `meal_id` propagated alongside `recipe_id`:

```python
insert_values = [
    {
        ...
        "recipe_id": rule.recipe_id,
        "meal_id": rule.meal_id,  # NEW — inherits from rule
        ...
    }
    ...
]
```

This is a 2-line change. `meal_id` on meal_events is nullable and the new check constraint permits `num_nonnulls <= 1`, so recipe-only rules keep setting `recipe_id` + `meal_id=NULL` (1 nonnull, valid); Meal-only rules set `meal_id` + `recipe_id=NULL` (1 nonnull, valid).

### Tests

- `test_meal_event_router_with_meals.py` (NEW):
  - Create happy in Meal mode; access-check 403 when user can't read the Meal's book; 404 on missing/archived Meal; XOR-reject when both FKs set (422, code `MEAL_EVENT_RECIPE_XOR_MEAL`).
  - Update mode-switch (Recipe → Meal → Recipe); `meal_summary` hydration on get + list.
  - Single-recipe path regression: existing create/get/list fixtures pass unchanged.
- `test_recurrence_rule_router_with_meals.py` (NEW) — parallel.
- `test_cooking_log_meal_fanout.py` (NEW):
  - Cook-log on a recipe event → one row, `recipe_id` set (regression).
  - Cook-log on a Meal event with 2 components → 1 Meal-level parent row + 2 recipe-level children with `parent_meal_log_id` set.
  - Recipe detail's "last cooked at" query (wherever it lives) still counts the fan-out children correctly (regression assertion on the existing count).
- `test_populate_from_calendar_with_meals.py` (NEW):
  - **Regression A (LOAD-BEARING)**: fixture with 5 recipe-only events, run `PopulateFromCalendar` before + after this epic's code, assert response JSON + DB rows are byte-identical.
  - **Dedupe A**: Meal with 2 components both specifying `1 tbsp olive oil` → 1 item, `quantity=2, unit="tbsp"`.
  - **Dedupe B**: same Meal on Monday + Wednesday within range → 2 items (1 per event), each with 2 tbsp (per-event separation preserved).
  - **Dedupe C**: mixed range of 3 recipe-only events + 2 Meal events → recipe items produced as before; Meal items produced via aggregate.
  - **Unit-variance**: Meal with two components specifying olive oil at `1 tbsp` and `15 ml` → 2 items (no cross-unit merge in v1).
  - **Unavailable component**: Meal with one archived component → populate skips it with `logger.warning`, doesn't fail overall; response `items_added` reflects only available ingredients.
  - **Null-unit**: Meal with two components specifying `2 eggs` (null unit) → 1 item with summed count.
  - **`source_meal_id` column**: every item created from a Meal-event expansion has it set; recipe-event items have it null.
- `test_aggregate_meal_ingredients.py` (NEW) — unit tests for the service function in isolation from the HTTP layer.
- `test_add_meal_to_shopping_list.py` (NEW) — the `POST /v1/meals/{meal_id}/add-to-shopping-list` handler: happy, 403 on non-reader, 403 on non-writer of shopping list, 404 on missing Meal, `meal_event_id=NULL` + `source_meal_id` on every row.
- `test_materialize_meal_rule.py` (NEW) — rolling-window materializer: rule with `meal_id` set produces events with `meal_id` inherited, title = Meal name; existing recipe-rule fixtures unchanged.
- `test_list_meals_autocomplete.py` (NEW) — `GET /v1/meals?q=...&limit=8` returns matching Meals scoped to readable books, excludes archived, honors limit.

**Coverage**: 100% branch, CI gate per CLAUDE.md. The new XOR validator, the new aggregate service, the new populate branch, and the new Meal-shopping endpoint are all fully covered by the fixture matrix above.

## Infrastructure Changes

**None.**

- **Migration**: one alembic revision. Column additions + `NOT VALID` check constraints + indexes + `shopping_list_items.source_meal_id` additive column + `cooking_logs` schema adjustments. All changes are additive or nullable-widening. Safe on prod-sized tables per the `NOT VALID` / `VALIDATE CONSTRAINT` pattern (SHARE UPDATE EXCLUSIVE lock during validate, not ACCESS EXCLUSIVE — concurrent reads + writes are fine).
- **No new AWS resources, no new env vars, no Dockerfile changes.**
- **Worker / Celery**: the existing `advance_recurrence_windows` task reuses the materializer; no beat-schedule or task-code changes beyond the 2-line materializer extension.
- **Deploy ordering**: standard. Alembic's linear `down_revision` chain enforces foundation migration → this migration. If foundation is not yet deployed when this migration runs, the migrator task fails fast on the missing `meals` table — a loud, unambiguous signal.
- **No shadow-migration / canary** needed — the change is strictly additive.

## Design Principles (refined)

1. **XOR enforced at three layers.** DB `CHECK (num_nonnulls(recipe_id, meal_id) <= 1)`, Pydantic `model_validator`, Flutter `assert` (debug mode). Server is the final authority; client assertion catches misuse in tests.
2. **Recipe mode is the default.** Every plan-meal entry point except "Plan for Date" from the Meal detail screen opens the sheet in Recipe mode. Zero regression for users who have no Meals.
3. **"Plan for Date" from Meal detail opens pre-filled Meal mode.** Meal is already picked; the user only chooses date/time/repeat. This is the one context where the default flips.
4. **Meal event rendering has ONE visual cue beyond the label: stack icon + "N recipes" caption.** Everything else — grid layout, tap affordance, swipe, reschedule — is identical to a recipe event. Caption copy comes from the shared helper so it doesn't drift from MealTile.
5. **Open Recipe disambiguation is a bottom sheet, not a full screen.** Title: "Which recipe?" The chooser omits unavailable components entirely (no dead rows).
6. **Shopping-list dedupe is sum-within-meal, per-event.** 1 tbsp + 1 tbsp olive oil within Kale Salad Meal → 2 tbsp one line. Same Meal on Monday + Wednesday → two separate 2-tbsp groups. Cross-unit merging (tbsp vs. ml) is **not done in v1** — produces separate lines.
7. **Unit normalization uses the live `unit_aliases` table**, not the draft's string-equality fallback. Verified: migration `20260418040000_create_unit_aliases.py` is shipped; `normalize_unit_display` is the call site.
8. **Point-in-time snapshot at populate time.** If a Meal's components change after an event was scheduled, the shopping-list populate uses the Meal's **current** components at the moment the user taps Add-to-Shopping-List. Not the components-at-schedule-time. This matches user intent ("buy what this Meal needs right now") and avoids a snapshot column.
9. **Component unavailability degrades gracefully, never catastrophically.** Archived component → skipped in populate with `logger.warning`; hidden in the chooser; greyed in the Meal detail screen's component list; the calendar tile + meal_event still render. The Meal event itself is never auto-deleted.
10. **Archived Meal handling.** If the Meal referenced by a meal_event is archived AFTER the event was scheduled, the event survives (not auto-cleaned). The calendar tile renders greyed with "(archived)" suffix. The populate path skips the event entirely with a warning. Rescheduling or marking as cooked is blocked (snackbar: "This Meal was archived — restore it to plan further").
11. **No participants semantics change.** `meal_event_participants` attach to the event, not to component recipes. Inviting a partner to a Meal event invites them to the whole Meal.
12. **Mark-as-Cooked: one Meal-level log + fan-out per-component children.** Meal detail surfaces display the parent row; recipe detail "last cooked" counts the fan-out children. Both views stay accurate from a single user action. (Was open question — resolved.)
13. **Migration is safe on live prod.** `NOT VALID` + `VALIDATE CONSTRAINT` does not ACCESS EXCLUSIVE the table; concurrent reads and writes proceed. Additive columns only. Downgrade reverses cleanly (with a cooking_logs safety assertion).
14. **`source_meal_id` on shopping_list_items is additive and nullable.** Every existing row has it null. No backfill needed. No constraint with `recipe_id` or `meal_event_id` — the field is purely descriptive provenance.
15. **Regression fixtures are LOAD-BEARING.** Recipe-only `PopulateFromCalendar` output must be byte-identical pre- and post-epic. Regression fixture A is non-optional in CI.

## File Structure

```
libraries/utils/utils/models/
  meal_event.py                              [MODIFY]  +meal_id, +ck_meal_events_recipe_xor_meal, +ix_meal_events_meal_id
  meal_recurrence_rule.py                    [MODIFY]  +meal_id, +ck_meal_recurrence_rules_recipe_xor_meal, +index
  cooking_log.py                             [MODIFY]  +meal_id, +parent_meal_log_id, recipe_id nullable, +ck_cooking_logs_target
  shopping_list_item.py                      [MODIFY]  +source_meal_id nullable FK

libraries/utils/utils/services/
  meal_service.py                            [MODIFY]  +aggregate_meal_ingredients(meal) -> list[AggregatedIngredient]

libraries/utils/utils/recurrence/
  materializer.py                            [MODIFY]  +meal_id inheritance in insert_values, +meal title resolution

services/migrator/migrations/versions/
  <yyyymmddhhmm>_add_meal_id_to_calendar_and_cooking_logs.py  [NEW]

services/api/src/schemas/
  meal_event.py                              [MODIFY]  +meal_id XOR validator, +meal_summary response
  recurrence_rule.py                         [MODIFY]  parallel
  shopping_list_item.py                      [MODIFY]  +source_meal_id in response

services/api/src/api/v1/meal_event/
  create_meal_event.py                       [MODIFY]
  update_meal_event.py                       [MODIFY]
  list_meal_events.py                        [MODIFY]
  get_meal_event.py                          [MODIFY]

services/api/src/api/v1/recurrence_rule/
  create_recurrence_rule.py                  [MODIFY]
  update_recurrence_rule.py                  [MODIFY]
  list_recurrence_rules.py                   [MODIFY]
  get_recurrence_rule.py                     [MODIFY]

services/api/src/api/v1/meals/
  list_meals.py                              [MODIFY]  +?q=... autocomplete params
  add_meal_to_shopping_list.py               [NEW]     POST /v1/meals/{id}/add-to-shopping-list

services/api/src/api/v1/shopping_list/
  populate_from_calendar.py                  [MODIFY]  +Meal expansion branch (recipe branch untouched)

services/api/src/api/v1/cooking_log/
  create_cooking_log.py                      [MODIFY]  +Meal fan-out path

app/lib/features/calendar/
  widgets/plan_meal_sheet.dart               [MODIFY]  +SegmentedButton, +MealAutocompleteField swap, +SingleChildScrollView
  widgets/meal_autocomplete_field.dart       [NEW]
  widgets/calendar_event_tile.dart           [MODIFY]  +Meal rendering (or inline in calendar_screen.dart)
  widgets/day_detail_sheet.dart              [MODIFY]
  widgets/meal_event_detail_sheet.dart       [MODIFY]  +Open Meal row, +chooser integration
  widgets/calendar_recipe_chooser_sheet.dart [NEW]     "Which recipe?" bottom sheet
  widgets/recurrence_field.dart              [MODIFY, minimal]
  services/meal_calendar_service.dart        [MODIFY]  +meal_id param path
  models/meal_event.dart                     [MODIFY]  +mealId, +mealSummary

app/lib/features/meals/
  meal_detail_screen.dart                    [MODIFY]  wire Plan-for-Date + Add-to-Shopping-List slots (remove tooltips)
  services/meal_service.dart                 [MODIFY]  +searchMeals, +addToShoppingList

app/lib/features/profile/recurring_plans/
  recurring_plans_screen.dart                [MODIFY]  +Meal rule rendering

services/api/tests/
  test_meal_event_router_with_meals.py       [NEW]
  test_recurrence_rule_router_with_meals.py  [NEW]
  test_cooking_log_meal_fanout.py            [NEW]
  test_populate_from_calendar_with_meals.py  [NEW]  +regression fixture A
  test_aggregate_meal_ingredients.py         [NEW]
  test_add_meal_to_shopping_list.py          [NEW]
  test_materialize_meal_rule.py              [NEW]
  test_list_meals_autocomplete.py            [NEW]
```

## Stories

### Story mcal-1 — Backend: migration + models for meal_id on calendar + cooking_logs + shopping_list_items

**Acceptance criteria:**

- One alembic revision `<yyyymmddhhmm>_add_meal_id_to_calendar_and_cooking_logs.py`:
  - `meal_events.meal_id` nullable FK `meals.id` ondelete SET NULL; `ix_meal_events_meal_id`; `ck_meal_events_recipe_xor_meal` = `num_nonnulls(recipe_id, meal_id) <= 1`, created NOT VALID then VALIDATE CONSTRAINT.
  - `meal_recurrence_rules.meal_id` nullable FK + `ix_meal_recurrence_rules_meal_id` + `ck_meal_recurrence_rules_recipe_xor_meal`, same NOT VALID pattern.
  - `cooking_logs`: drop NOT NULL from `recipe_id`; add `meal_id` nullable FK; add `parent_meal_log_id` nullable self-FK; add `ck_cooking_logs_target` (two-clause constraint per Design § 12).
  - `shopping_list_items.source_meal_id` nullable FK (additive, no constraint).
- Models updated in `meal_event.py`, `meal_recurrence_rule.py`, `cooking_log.py`, `shopping_list_item.py` to match.
- **`downgrade()`** reverses all changes; cooking_logs `recipe_id` NOT NULL restoration is guarded by `SELECT COUNT(*) FROM cooking_logs WHERE recipe_id IS NULL` assertion.
- Migration round-trip (up + down + up) leaves zero orphan artifacts.
- `npx nx run migrator:migrate` runs clean against a fresh DB with foundation applied first.
- **Test**: a model-level test verifies the CHECK constraint: inserting a meal_event with both `recipe_id` and `meal_id` set raises `IntegrityError`; either alone succeeds; neither set (free-text) succeeds.
- **100% coverage** on all new model branches.

### Story mcal-2 — Backend: `aggregate_meal_ingredients` service + dedupe correctness

**Acceptance criteria:**

- New function in `libraries/utils/utils/services/meal_service.py` per spec in Backend Changes § Service.
- Dedupe key: `(ingredient_id, normalize_unit_display(unit, session))`. Unit normalization uses the live `unit_aliases` cache (no fallback — the table is live).
- Handles: same-unit merge (2×1 tbsp → 2 tbsp), cross-unit NOT merged (1 tbsp + 15 ml → 2 lines), null-unit ingredients, zero-ingredient components, archived-recipe components (skip with warning).
- Returns `list[AggregatedIngredient]` — `(ingredient_id, ingredient_name, category, summed_quantity, normalized_unit, contributing_recipe_ids)`.
- `test_aggregate_meal_ingredients.py` covers all six cases at 100% branch.

### Story mcal-3 — Backend: meal_event + recurrence_rule endpoints accept meal_id XOR

**Acceptance criteria:**

- `POST /v1/meal-events` accepts `{meal_id}` XOR `{recipe_id}`. Pydantic `model_validator(mode="after")` rejects both-set with 422 code `MEAL_EVENT_RECIPE_XOR_MEAL`. Auth-fail with 403 when the user can't read the Meal's book; 404 if Meal missing or archived.
- `PATCH /v1/meal-events/{id}` supports mode-switching (clearing the unused FK).
- `GET /v1/meal-events` hydrates `meal_summary` when `meal_id` set (via `selectinload` chain per Backend Changes § Handlers). Response shape backward-compatible — old clients ignore the new key.
- Parallel treatment for `/v1/meal-recurrence-rules` in `create_recurrence_rule.py` / `update_recurrence_rule.py` / `list_recurrence_rules.py` / `get_recurrence_rule.py`.
- **Regression**: recipe-only create/update/list/get fixtures pass unchanged; test asserts response bodies are byte-identical to pre-epic baseline for recipe-only events.
- **100% branch coverage**: happy (both modes), XOR reject, 404, 403, mode-switch, hydration with + without meal_summary.

### Story mcal-4 — Backend: `PopulateFromCalendar` Meal expansion + sum-within-meal dedupe (LOAD-BEARING)

**Acceptance criteria:**

- `populate_from_calendar.py` gains a sibling branch for `meal_event.meal_id is not None`. The existing recipe-branch code is **not modified**.
- Meal-event items get `recipe_id=NULL`, `meal_event_id=<event.id>`, `source_meal_id=<event.meal_id>`.
- Dedupe key within the Meal: `(ingredient_id, normalized_unit)` — sum quantities. Across events: existing per-event separation (keyed by `(ingredient_id, meal_event_id)` in the `existing_items` dedupe).
- Unavailable component → skip with `logger.warning("meal-event populate: component {recipe_id} unavailable", ...)`; don't fail.
- Pantry parity: when `check_pantry=true`, the Meal-branch reduces `needed_quantity` by pantry stock the same way the recipe branch does.
- **Regression fixture A (LOAD-BEARING)**: `services/api/tests/fixtures/populate_calendar_recipe_only.json` captures the pre-epic response for 5 recipe-only events; the test re-runs post-epic and asserts byte-identical response.
- **Dedupe fixtures**:
  - (A) Meal with 2 components both `1 tbsp olive oil` → 1 item, `quantity=2`.
  - (B) Same Meal on Monday + Wednesday in range → 2 items each with 2 tbsp (per-event separation).
  - (C) Mixed 3 recipe + 2 Meal events → recipe items produced as before; Meal items added correctly.
  - (D) Unit variance: `1 tbsp` + `15 ml` olive oil → 2 lines.
  - (E) Null-unit: 2 eggs + 2 eggs → 1 line, 4 eggs.
  - (F) Archived component → skipped; `items_added` reflects only available ingredients; warning logged.
- **100% branch coverage** on the new branch. Existing recipe-branch coverage unchanged.

### Story mcal-5 — Backend: Meal autocomplete list param + `add_meal_to_shopping_list` endpoint

**Acceptance criteria:**

- `GET /v1/meals?q=<text>&limit=8` returns matching Meals (name ILIKE or description ILIKE), scoped to readable books, excludes archived. Limit max 20 (autocomplete default 8). Hydrates `component_count` + top-4 thumbs for the picker.
- `POST /v1/meals/{meal_id}/add-to-shopping-list` accepts `{shopping_list_id: UUID}`. Requires read access on the Meal + write access on the shopping list. Calls `aggregate_meal_ingredients(meal)`; inserts `ShoppingListItem` rows with `meal_event_id=NULL`, `source_meal_id=meal.id`. Response: `{items_added, items, meal_summary}`.
- Unavailable component → skipped with warning; partial success is fine.
- **100% branch coverage**: happy, 403 non-reader of Meal, 403 non-writer of list, 404 missing Meal, 404 missing list, partial-unavailability.

### Story mcal-6 — Backend: rolling-window materializer supports Meal rules + cooking log fan-out

**Acceptance criteria:**

- `materializer.py` `_resolve_title` checks `rule.meal_id` first, falls back to `recipe_id`, then `rule.title or "Meal"`. The `insert_values` dict propagates `meal_id` alongside `recipe_id`.
- Materialized events with `meal_id` set correctly satisfy the CHECK constraint (only one of recipe_id / meal_id non-null).
- `test_materialize_meal_rule.py`: rule with `meal_id` produces events with `meal_id` set, title = Meal name; recipe-rule regression fixture unchanged.
- Cooking-log create handler: when `meal_event_id` refers to an event with `meal_id` set, creates one parent log + per-component fan-out children; when `recipe_id` set, single-row as today.
- `test_cooking_log_meal_fanout.py`: recipe-event regression; 2-component Meal event → 1 parent + 2 children; recipe "last cooked" query returns the correct count for component recipes.
- **100% branch coverage** on the new paths.

### Story mcal-7 — Flutter: plan-meal sheet Recipe/Meal SegmentedButton + MealAutocompleteField

**Acceptance criteria:**

- `plan_meal_sheet.dart` renders a `SegmentedButton<PlanMealType>` at the top of the picker row: Recipe | Meal. Default: Recipe, except when launched with `initialPlanMealType: PlanMealType.meal` → Meal with pre-filled linked chip.
- Body wrapped in `SingleChildScrollView` — SE-sized fixture no longer clips Save.
- Toggling to Meal mounts `MealAutocompleteField`; toggling back to Recipe restores `RecipeAutocompleteField`.
- `_save()` dispatches `createMealEvent` / `createRecurrenceRule` with `mealId` XOR `recipeId` (never both); debug-mode `assert` catches misuse before the network call.
- Entry points verified: calendar FAB → Recipe; day-tap → Recipe; recipe detail "Plan for…" → Recipe pre-filled; Meal detail "Plan for Date" → Meal pre-filled.
- **Widget tests**: SegmentedButton renders; toggle swaps autocomplete; save dispatches correct mutation; small-screen fit; entry-point default matrix.

### Story mcal-8 — Flutter: calendar grid + day sheet + detail sheet + chooser

**Acceptance criteria:**

- Calendar grid tile + day sheet render meal_id events as "MealName" + `Icons.layers` + muted "N recipes" caption (using shared `kMealComponentCountLabel` helper). Recipe events unchanged (regression fixture).
- `meal_event_detail_sheet.dart` shows "Open Meal" row when `mealId` set → `context.push('/meals/:id')`. "Open Recipe" action: 1 available → direct push; ≥2 → `CalendarRecipeChooserSheet`.
- `calendar_recipe_chooser_sheet.dart` (NEW): bottom sheet, title "Which recipe?", lists available components (omits unavailable), tap pushes `/recipes/:id`.
- Existing Reschedule / Unschedule / Mark-as-Cooked unchanged in UI; Mark-as-Cooked posts to the updated cooking-log endpoint (mcal-6 handles the fan-out server-side).
- **Widget tests**: tile rendering for both event types; regression fixture for recipe events; chooser appears for multi-component Meals; Open Meal navigates.

### Story mcal-9 — Flutter: Meal detail action-bar wiring + recurring plans screen

**Acceptance criteria:**

- `meal_detail_screen.dart` **Plan for Date** action: tooltip removed, action enabled, launches `PlanMealSheet` with Meal pre-filled in Meal mode.
- `meal_detail_screen.dart` **Add to Shopping List** action: tooltip removed, action enabled, launches shopping-list picker, on pick calls `MealService.addToShoppingList(mealId, listId)`.
- Snackbar on success: "Added N items from <MealName>". Snackbar on partial-unavailability: "Added N items (some components unavailable)."
- `recurring_plans_screen.dart` renders Meal rules as "Every Monday dinner · Kale Salad Meal (2 recipes)". Tap opens plan-meal sheet in Meal mode pre-filled. End Series works unchanged.
- **Widget tests**: action-bar buttons live (no tooltip); Plan-for-Date opens correct sheet; Add-to-Shopping-List end-to-end mock; recurring rule row rendering.

## Dependencies

- **Blocks**: `epic-meals-sharing-and-ai` (the last Meals epic). Sharing + AI build on top of calendar integration for meal-pairing UX.
- **Depends on**:
  - `epic-meals-create-and-view` (foundation) — requires `meals` + `meal_recipes` tables and the foundation action-bar slot contract.
  - `epic-meals-discoverability` (landed) — not a hard dependency; parallelizable. But `meal_tile.dart` + `kMealComponentCountLabel` helper live in foundation; discoverability's search-extensions are orthogonal.
  - `epic-review-import-ingredient-polish` → `unit_aliases` table: **live and verified**. No fallback code path needed at ship.
- **Parallelizable with**: nothing in the Meals family after this epic (sharing is the last).

## Open Questions

**All four open questions are resolved:**

- **Mark-as-Cooked on a Meal event** → **one Meal-level CookingLog + per-component fan-out children via `parent_meal_log_id` FK**. Preserves both Meal-level cook-history ("Cooked the Kale Salad Meal on 4/17") and recipe-level "last cooked" accuracy.
- **Unit normalization fallback** → **not needed**. `unit_aliases` is live (migration `20260418040000_create_unit_aliases.py` shipped; `normalize_unit_display` is the call site). The "degraded dedupe mode" fallback in the draft is carried as a documented note only.
- **Open-Recipe chooser copy** → **"Which recipe?"** (terse, matches iOS/Material chooser convention).
- **Plan-meal toggle default** → **Recipe by default everywhere except "Plan for Date" from Meal detail**, which opens Meal mode pre-filled.

**Carrying forward to `epic-meals-sharing-and-ai`** (the last epic):

- The **shared `kMealComponentCountLabel(int n)` helper** exported from foundation's `meal_tile.dart` is now referenced by calendar surfaces (tile, day sheet, recurring plans screen) AND will be referenced by sharing surfaces (shared-meal card previews, public meal page). Sharing epic should NOT duplicate the format string.
- The **Meal detail action bar contract** is now five-of-six live in production: Favorite, Plan-for-Date, Add-to-Shopping-List, Archive, Edit. Share is the last disabled slot — sharing epic wires it.
- The **`meals.share_token` column** exists on the Meal model from foundation but no handler reads or writes it. Sharing epic owns the read/write path; the column is ready.
- **Cross-epic `num_nonnulls` constraint naming pattern**: `ck_<table>_<semantic>_xor_<semantic>`. Sharing epic, if it introduces similar XOR columns (e.g. share-token-type), should follow the same pattern.
- The **cooking-log fan-out model** (`parent_meal_log_id`) is now the canonical "one action → one parent row + N child rows" pattern. Any future Meal-level action that needs to reconcile with per-component histories (rating-a-Meal, annotating-a-Meal, etc.) should reuse the parent/child FK idea from this epic.

**Nothing to escalate to the user.**
