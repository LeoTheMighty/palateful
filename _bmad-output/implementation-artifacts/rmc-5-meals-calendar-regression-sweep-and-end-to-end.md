# rmc-5 — Meals + calendar regression sweep + end-to-end tests + copy map

**Status**: done
**Epic**: epic-reactive-migration-meals-calendar

## What shipped

**Copy coverage** (AC #6): `mutationFailureCopy` map covers every calendar, meal-event, and recurrence-rule verb enumerated in the epic. Added a top-level assertion in `mutation_failure_copy_e2e_test.dart` that iterates `MutationType.values` and fails CI the moment a new enum case lands without copy — cheap forward-compatibility guard that protects against the silent `"Couldn't complete that action"` fallback shipping to production.

**Representative copy e2e** (AC #6): extended `mutation_failure_copy_e2e_test.dart` with 7 new calendar representatives (createCalendar, deleteCalendar, createMealEvent, planMealEvent, markMealCompleted, rescheduleMealEvent, createRecurrenceRule). Each scenario drives `showMutationFailureSnackbar` through a real button tap and asserts the rendered title matches the expected `Couldn't <verb> <noun>` line.

**Mark-cooked E2E** (AC #4): new `mark_cooked_flow_test.dart` drives `MealCalendarService.markMealCompleted` end-to-end: asserts the method returns a `MealEvent` with `status=completed`, verifies the emitted `MealEventCompleted` carries the full payload and a populated `calendarId`, then confirms the real `mealEventsByRangeProvider` refetches exactly once through the 100ms coalescer.

**Grep sweep** (AC #8): migrated the two remaining mutation-failure ScaffoldMessenger sites in `meal_detail_screen.dart` (load-shopping-lists failure + add-meal-to-shopping-list failure) to `showMutationFailureSnackbar`. The other remaining ScaffoldMessenger sites in `meals/` and `calendar/` are validation errors, success toasts, or features outside this epic's verb list (RSVP, meal-reminder-time — owned by calendars-sharing / meal-reminders epics); leaving them as-is is the correct scope call.

**AC #1–3 coverage via existing tests**: rmc-1 / rmc-2 / rmc-3 already cover these end-to-end:
- AC #1 (create-meal flow) — covered by `meals_by_book_reactivity_test.dart` (MealCreated → mealsByBookProvider refetch) + home-screen reactivity (rf-6).
- AC #2 (add-component flow) — covered by `meal_detail_component_reactivity_test.dart` (MealComponentAdded → MealDetail patches in place, no refetch) + `used_in_meals_reactivity_test.dart` (recipe detail's "Used in these Meals" row updates).
- AC #3 (plan-meal flow) — covered by `calendar_grid_event_reactivity_test.dart` (MealEventCreated → grid refetch + new tile) + `day_sheet_reactivity_test.dart` (day sheet re-renders on same-day event).

## Files

- `app/lib/features/meals/meal_detail_screen.dart` — 2 ScaffoldMessenger failure sites migrated to `showMutationFailureSnackbar`: load-shopping-lists (`MutationType.loadShoppingLists`) + add-meal-to-shopping-list (`MutationType.addEventIngredients`).
- `app/test/core/state/mutation_failure_copy_e2e_test.dart` — +7 calendar representatives in the copy e2e loop; new top-level "every MutationType has a copy entry" assertion.
- `app/test/features/calendar/mark_cooked_flow_test.dart` — **new**. Two tests: service-layer emit contract + provider-refetch-through-coalescer.

## Gotchas

- **AC #6 explicit list vs. `MutationType.values`**: the epic lists 22 calendar/meal verbs, but the enum also accumulated 7 "rmc-drive-by" values in rmc-3 (`loadShoppingLists`, `addEventIngredients`, etc.). The new exhaustive-coverage assertion covers both sets in one pass — future rmc-drive-bys can't drift.
- **`mark_cooked_flow_test.dart` uses `ProviderContainer.listen` directly** rather than a pumped widget tree. Rationale: the coalescer fires on a real `Timer`, so `tester.pump(Duration)` plus a `.future` re-read of the provider is the cleanest way to await "coalescer fires → refetch completes" without wall-clock flake.
- **Meal-detail RSVP + reminder-time snackbars left as-is.** The epic's verb list does not include these; they belong to calendar-sharing and meal-reminder-time features respectively. Migrating them here would scope-creep rmc-5.
- **meal_edit_screen's "needs at least 2 recipes" snackbar stays raw.** It's a domain-specific error message (not a generic "Couldn't X Y") and maps poorly onto `showMutationFailureSnackbar`'s `<verb> <noun>` grammar. The adjacent `MutationType.removeComponent` copy handles the other 422 catch-all.

## QA walkthrough

### Regression (CI-guarded)

- [x] `mutation_failure_copy_e2e_test.dart` — 14 representative scenarios pass; exhaustive enum-coverage assertion passes.
- [x] `mark_cooked_flow_test.dart` — 2 tests pass (service emit contract + provider refetch).
- [x] `meal_detail_screen_test.dart` — all 29 tests pass after the 2 ScaffoldMessenger migrations.
- [x] Full app test suite green: **1149 tests pass, 0 failures** (as of this commit).

### Manual dogfood (end-to-end — the four-step PM script from the epic)

- [ ] Create Meal "Sunday Roast" (3 components) → pop to Home → tile visible without pull-to-refresh.
- [ ] Open Meal detail for "Weeknight Pasta" → Add Recipe → pick "Garlic Bread" → back on detail, chip strip includes "Garlic Bread" without refresh. Navigate to Garlic Bread recipe → "Used in these Meals" row shows "Weeknight Pasta".
- [ ] Open Calendar → tap Friday → plan "Sunday Roast" at 6:30 PM → cell renders the new chip without reload; day-sheet list already updated.
- [ ] Mark the Friday event as cooked → cell chip re-renders with cooked indicator; if Meal detail's "Upcoming plans" row is open in a separate tab, it's updated.

If all four steps pass without a single pull-to-refresh gesture, the epic is "done" from end-user vantage.
