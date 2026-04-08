# Investigation: Calendar / Meal Planning UX

**Date:** 2026-03-22
**Status:** Investigation Complete
**Pain point:** "Calendar screen is a little confusing and I'm not sure how to plan a meal from there. Seems like it's missing a '+' button somewhere."

---

## Executive Summary

The Palateful calendar screen currently displays a week view of scheduled meal events but provides **no visible way to add a new meal from the calendar itself**. There is no "+" button, no FAB, no tappable empty slot, and no contextual "add" affordance anywhere on the screen. The only way to plan a meal is to navigate away to a recipe detail screen, open a three-dot overflow menu, select "Plan for...", pick a date, and pick a meal type -- a minimum of 5 taps starting from a completely different screen. For a feature that is the calendar's primary purpose ("plan meals"), this is a critical discoverability and usability failure.

The calendar screen also lacks several affordances found in competitor apps: there is no ability to tap on a day to expand/add, no per-day "+" button, no per-meal-slot structure showing breakfast/lunch/dinner rows, no drag-and-drop, and no quick-add for free-text meals (e.g., "eating out"). The empty state for each day simply says "No meals planned" with no actionable hint about how to plan one.

The recommended approach is to: (1) add a prominent floating action button to the calendar screen that opens a meal creation flow, (2) add tappable "+" icons on each day row, (3) restructure the day view to show meal-type slots (breakfast, lunch, dinner, snack) with inline add affordances, (4) improve empty states with actionable guidance, and (5) add a "quick add" option for non-recipe meals.

---

## Current State Analysis

### Calendar Screen Architecture

The calendar lives at `/calendar` as one of five bottom navigation tabs (Home, Books, Cart, **Calendar**, Profile).

**File:** `app/lib/features/calendar/calendar_screen.dart`

The screen is a `StatefulWidget` that:
- Shows a **week view** (Mon-Sun) with left/right chevron navigation in the app bar
- Loads events for the displayed week via `MealCalendarService.listMealEvents(start, end)`
- Groups events by day into `Map<DateTime, List<MealEvent>>`
- Renders each day as a card (`_buildDayColumn`) containing event tiles or "No meals planned" text
- The app bar has a single action: a shopping cart icon that generates a weekly shopping list from planned meals

### How Meals Are Currently Added

There are exactly **two entry points** for creating meal events, and **neither is on the calendar screen**:

#### Entry Point 1: Recipe Detail Screen (Primary)

**File:** `app/lib/features/recipes/recipe_detail_screen.dart` (line 610-647)

1. User navigates to a recipe detail page
2. Taps the three-dot overflow `PopupMenuButton` in the app bar
3. Selects "Plan for..." (item 2 of ~8 menu items)
4. A `PlanMealSheet` bottom sheet appears with date picker and meal type selector
5. User picks a date and meal type, then taps "Add to Calendar"

**Minimum taps from calendar: 5+** (navigate to Home > find recipe > open recipe > tap overflow > tap "Plan for..." > pick date > save)

#### Entry Point 2: Calendar Screen Reschedule (Edit Only)

**File:** `app/lib/features/calendar/calendar_screen.dart` (line 281-335)

1. User long-presses an existing meal event tile
2. A bottom sheet appears with Reschedule / Add to shopping list / Remove
3. "Reschedule" opens the same `PlanMealSheet` in edit mode

This flow is **edit-only** -- it cannot create new events.

### PlanMealSheet (The Creation/Edit Widget)

**File:** `app/lib/features/calendar/widgets/plan_meal_sheet.dart`

This bottom sheet handles both creation and rescheduling. It requires:
- `recipeId` (String, required) -- always requires a recipe
- `recipeName` (String, required)
- Optional `eventId` for edit mode
- Optional `initialDate` and `initialMealType`

**Critical limitation:** The sheet **always requires a recipe ID**. There is no way to create a free-text meal event (e.g., "Eating out", "Leftovers", "Partner's cooking night") without first having a recipe in the system. The API supports recipe-less events (`recipe_id` is optional in `CreateMealEvent.Params`), but the Flutter UI does not expose this capability.

### What the Calendar Screen Shows

Each day card contains:
- A **day header** with date number in a circle (filled chocolate color for today) and abbreviated day name
- **Event tiles** with: recipe thumbnail or meal-type icon, event title, meal-type badge (Breakfast/Lunch/Dinner/Snack), cook time
- **Empty state:** Plain text "No meals planned" in disabled gray -- no action hint, no tap target, no button

Tapping an event tile navigates to the recipe detail screen. Long-pressing shows the options sheet (reschedule/remove). There is no visual indicator of meal slots (breakfast/lunch/dinner) when the day is empty.

### App Bar Actions

The calendar app bar contains:
- **Left/right chevrons** for week navigation
- **Week label** (e.g., "Mar 16-22")
- **Shopping cart icon** (single action button) to generate a weekly shopping list

There is **no "+" button, no FAB, and no "Add Meal" action** anywhere on the calendar screen.

### API Capabilities (Underutilized)

**File:** `services/api/src/api/v1/meal_event/create_meal_event.py`

The API's `CreateMealEvent` endpoint supports:
- `title` (required) -- can be any text, not just recipe names
- `recipe_id` (optional) -- meals without recipes are fully supported
- `meal_type` (required) -- breakfast, lunch, dinner, snack
- `scheduled_at` (required) -- date and time
- `is_shared` (optional) -- for collaborative meal planning
- `is_recurring` (optional) -- with `recurrence_rule` for repeated meals
- `description` (optional) -- free text notes
- Notification preferences (`notify_prep_start`, `notify_cook_start`)

The API is significantly more capable than what the Flutter UI exposes. Recurring meals, free-text meals, descriptions, and notification preferences are all supported server-side but completely inaccessible from the calendar screen.

### Database Model

**File:** `libraries/utils/utils/models/meal_event.py`

The `MealEvent` model supports:
- Status workflow: planned -> shopping -> prepping -> cooking -> completed | skipped
- Recurring events with parent/child relationships
- Participant system for shared meal planning
- Prep steps for complex cooking workflows
- Shopping list generation per event

### Home Screen Integration

**File:** `app/lib/features/home/home_screen.dart` (lines 120-141, 605-670)

The home screen shows a "hero card" for today's first meal event (if it has a recipe with an image). This provides a nice at-a-glance view of what's planned but does not link back to the calendar or provide a way to add more meals.

---

## Usability Issues Identified

### Critical Issues

1. **No add affordance on the calendar screen.** This is the most fundamental UX failure. The calendar's primary purpose is meal planning, but there is no visible way to add a meal. Users must leave the calendar entirely, find a recipe, and use a buried menu option. This directly matches the user's reported pain point.

2. **PlanMealSheet requires a recipe ID.** The bottom sheet that creates events mandates a `recipeId`, but the API allows recipe-free events. Users cannot log "eating out", "leftovers", "ordering pizza", or any non-recipe meal.

3. **Empty day states are passive.** "No meals planned" text in gray provides no guidance on what to do next. Empty states should be actionable -- telling the user how to plan a meal and providing a tap target to do so.

### Major Issues

4. **Overflow menu burial.** The "Plan for..." action on recipe detail is hidden in a `PopupMenuButton` alongside 7 other actions (Add to Cart, Share Link, Share, Move, Copy, Fork, Archive). First-time users are unlikely to discover it.

5. **No meal-slot structure in the day view.** Days show events as a flat list without breakfast/lunch/dinner/snack segmentation. Users cannot see at a glance which meal slots are unfilled. This makes it hard to plan a balanced day of meals.

6. **No inline add per day.** Even if there were a global FAB, per-day "+" buttons (common in competitor apps) would let users add a meal to a specific day with one tap, pre-filling the date.

7. **Long-press discoverability.** The only way to access reschedule/delete is via long-press, which is an invisible gesture. There is no visual hint (like an options icon) that this interaction exists.

### Minor Issues

8. **No visual differentiation by meal type within a day.** Events are listed vertically with small meal-type badges, but there are no section headers or slot lanes for breakfast/lunch/dinner. Multiple events of different types blend together.

9. **Week navigation only.** Users cannot jump to a specific date, switch to month view, or return to "today" with one tap. They must chevron through weeks one at a time.

10. **No drag-and-drop.** Users cannot rearrange meals between days or change meal types by dragging, which is a standard pattern in competitor meal planning apps.

11. **No "today" quick-return button.** If a user navigates several weeks forward or backward, there is no way to quickly return to the current week other than repeatedly tapping the chevron.

---

## Research Findings

### Competitor Calendar Patterns

#### Plan to Eat
- **Week and month view toggle** in the upper left corner
- **Drag-and-drop** on both web and mobile: tap-and-hold on a recipe to move it to any day or meal slot
- **Meal slot structure**: days are divided into Breakfast, Lunch, Dinner, Snack sections with inline "+" buttons per slot
- **Recipe browser sidebar** (web) or search overlay (mobile) for adding recipes directly to the planner
- **Leftovers planning**: users can mark portions as leftovers and move them to other days

#### Eat This Much
- **Auto-generation**: the app fills the weekly calendar automatically based on nutritional goals
- **Day view** with clear meal-type sections (Meal 1, Meal 2, Meal 3, Snack)
- **Per-meal regenerate/swap buttons** for quick recipe changes
- **"Mark as eaten"** action for tracking
- **Inline recipe search** within each meal slot

#### Mealime
- **Simplified week view** with recipes displayed as cards per day
- **Tap-to-add** pattern: tapping an empty slot opens recipe suggestions
- **Smart grocery list** auto-generated from the meal plan
- **Dietary preference filtering** integrated into the planning flow

#### General Industry Patterns (2025-2026 Trends)
- **Drag-and-drop** is the dominant interaction pattern for meal planning calendars
- **Per-slot "+" buttons** (breakfast/lunch/dinner) are standard in nearly all competitors
- **Quick-add / free-text meals** are supported by most apps for non-recipe entries
- **AI-powered suggestions** are emerging: apps suggest recipes based on time of day, dietary history, pantry contents, and season
- **Grocery list integration** directly from the calendar view is expected functionality
- **Week view is primary**, with month view as secondary for longer-range planning

### Key UX Principles for Meal Planning Calendars

1. **The add action must be immediately visible.** Users should never wonder "how do I add a meal?" The answer should be visually obvious.
2. **Meal slots create structure.** Showing breakfast/lunch/dinner sections per day gives users mental scaffolding and makes empty slots visible and tappable.
3. **Reduce decision friction.** Pre-filling the date (from the tapped day) and defaulting the meal type (from the tapped slot) eliminates two of three decisions needed to plan a meal.
4. **Support non-recipe meals.** Real life includes eating out, leftovers, meal prep from batch cooking, and "figure it out later" placeholders. The calendar should accommodate all of these.
5. **Make empty states inviting, not dead-ends.** An empty day should feel like an opportunity ("Tap + to plan your meals") not a void ("No meals planned").

---

## Proposed UX Improvements

### Improvement 1: Floating Action Button on Calendar Screen

Add a FAB to the calendar screen, matching the pattern already used on Home (add recipe), Books (add book), Cart (add list), and Recipe Book Detail (add recipe).

**Wireframe description:**
- A chocolate-colored circular FAB in the bottom-right corner with a "+" icon
- Tapping it opens a new "Add Meal" bottom sheet (not the existing `PlanMealSheet`)
- The sheet presents two options: "Choose a Recipe" and "Quick Add" (free text)
  - "Choose a Recipe" opens a searchable recipe picker, then the date/meal-type selector
  - "Quick Add" shows a text field for title, date picker, and meal type selector
- The date defaults to the currently viewed week's first empty day (or today if in current week)

### Improvement 2: Per-Day "+" Button in Day Header

Add a small "+" icon button to the right side of each day's header row.

**Wireframe description:**
```
[24] Mon                                    [+]
  [event tile...]
  [event tile...]

[25] Tue                                    [+]
  No meals planned
```
- Tapping "+" opens the same Add Meal flow but with the date pre-filled to that day
- The "+" is always visible, not hidden behind a gesture
- Uses a subtle but tappable `IconButton` with `Icons.add` in `AppColors.textTertiary`

### Improvement 3: Meal-Slot Structure Within Each Day

Restructure the day card to show meal-type sections (breakfast, lunch, dinner) with inline add affordances for empty slots.

**Wireframe description:**
```
[24] Mon                                    [+]
  Breakfast
    [Avocado Toast]  [thumbnail]  20 min   >
  Lunch
    + Add lunch                    (tappable)
  Dinner
    [Pasta Carbonara] [thumbnail] 45 min   >
  Snack (only shown if events exist or user explicitly adds)
```
- Each meal type is a labeled section within the day card
- Filled slots show the event tile as currently designed
- Empty slots show a subtle "+ Add [meal type]" text in tappable muted style
- Tapping an empty slot opens Add Meal with both date AND meal type pre-filled (only one decision remaining: which recipe)
- Snack section only appears if a snack is planned or if the user taps the day "+"

### Improvement 4: Actionable Empty States

Replace passive "No meals planned" text with interactive empty state content.

**Wireframe description:**
- For a day with zero events:
  ```
  [24] Mon                                    [+]
    Tap + to plan breakfast, lunch, or dinner
  ```
- For the overall calendar when the entire week is empty:
  ```
  [illustration/icon]
  No meals planned this week
  Tap + to start planning, or add meals
  from any recipe's detail page.
  [Plan a Meal] (primary button)
  ```

### Improvement 5: Quick Add for Non-Recipe Meals

Support creating meal events without a linked recipe, leveraging the existing API capability.

**Wireframe description:**
The "Quick Add" flow from the FAB or per-day "+":
```
Quick Add Meal
----------------------------
Title:  [Eating out at Sushi Place    ]
Date:   [Today                      >]
Meal:   [Breakfast] [Lunch] [Dinner] [Snack]
                      ^^^^^ (selected)
----------------------------
        [Add to Calendar]
```
- Simple text field for title
- Same date picker and meal type selector as PlanMealSheet
- No recipe required
- Useful for: eating out, leftovers, partner cooking, meal prep days, "TBD" placeholders

### Improvement 6: "Today" Quick-Return and View Controls

Add navigation improvements to the calendar app bar.

**Wireframe description:**
```
AppBar: [<] Mar 16-22 [>]    [Today] [cart]
```
- Add a "Today" text button that jumps back to the current week
- Only visible when the user has navigated away from the current week

---

## Recommendations (Prioritized)

### P0 -- Must Have (addresses the reported pain point directly)

| # | Improvement | Effort | Impact |
|---|------------|--------|--------|
| 1 | **Add FAB to calendar screen** | Small (1-2 hours) | Eliminates the core discoverability problem. Users immediately see they can add meals. |
| 2 | **Add per-day "+" buttons** | Small (1-2 hours) | Lets users add a meal to a specific day with one tap, pre-filling the date. |
| 3 | **Support free-text meals (Quick Add)** | Medium (3-4 hours) | Removes the hard requirement for a recipe. The API already supports this; the UI just needs to allow it. |

### P1 -- Should Have (significantly improves the experience)

| # | Improvement | Effort | Impact |
|---|------------|--------|--------|
| 4 | **Meal-slot structure within days** | Medium (4-6 hours) | Makes empty meal slots visible and tappable. Provides breakfast/lunch/dinner scaffolding. |
| 5 | **Actionable empty states** | Small (1-2 hours) | Guides new users and makes the calendar feel alive even when empty. |
| 6 | **"Today" quick-return button** | Small (<1 hour) | Quality-of-life improvement for navigation. |

### P2 -- Nice to Have (competitive parity features)

| # | Improvement | Effort | Impact |
|---|------------|--------|--------|
| 7 | **Recipe search/picker integrated in add-meal flow** | Medium (4-6 hours) | Currently users must know the recipe first. An inline search would let them discover and plan in one flow. |
| 8 | **Tap (not just long-press) for event options** | Small (1-2 hours) | Add a visible "..." icon on event tiles for discoverability. |
| 9 | **Month view toggle** | Large (8-12 hours) | Useful for longer-range planning but not critical for MVP meal planning. |

### P3 -- Future Consideration

| # | Improvement | Effort | Impact |
|---|------------|--------|--------|
| 10 | **Drag-and-drop meal rescheduling** | Large (12-16 hours) | Industry standard for meal planning but complex to implement in Flutter. |
| 11 | **AI recipe suggestions per slot** | Large (8-12 hours) | Suggest recipes based on time of day, recent meals, pantry contents. |
| 12 | **Recurring meal template support in UI** | Medium (6-8 hours) | API supports recurrence rules but UI has no way to create them. |

---

## Technical Considerations

### Adding the FAB (P0)

The calendar screen's `build` method returns a `Scaffold` with no `floatingActionButton` property set. Adding one follows the exact same pattern used in five other screens in the app:
- `home_screen.dart` -- `FloatingActionButton` for adding recipes
- `recipe_books_screen.dart` -- `FloatingActionButton` for adding books
- `cart_screen.dart` -- `FloatingActionButton.extended` for adding lists
- `recipe_book_detail_screen.dart` -- `FloatingActionButton` for adding recipes
- `recipe_book_members_screen.dart` -- `FloatingActionButton` for inviting members

**Key file to modify:** `app/lib/features/calendar/calendar_screen.dart`

The existing `PlanMealSheet` widget needs modification to support optional `recipeId` (for quick-add flow) or a new sheet widget needs to be created that acts as a routing sheet ("Choose a Recipe" vs. "Quick Add").

### Modifying PlanMealSheet for Quick Add

The `PlanMealSheet` currently has `recipeId` as a required parameter. For quick-add support:
- Make `recipeId` optional
- Add a `title` text field when no recipe is provided
- The `_save` method already handles the create path; it just needs to allow `recipeId` to be null
- The `MealCalendarService.createMealEvent` method already accepts `recipeId` as optional

### Recipe Picker Widget

For the "Choose a Recipe" flow, a new recipe search/picker widget is needed. The app already has search infrastructure:
- `app/lib/features/search/search_screen.dart` -- full search screen with API integration
- `app/lib/core/services/api_client.dart` -- `searchRecipes(query)` method exists
- A simplified version could be a bottom sheet with a search bar and scrollable list of recipe results

### Per-Day "+" Buttons

This requires modifying `_buildDayColumn` in `calendar_screen.dart` to add an `IconButton` to the day header `Row`. The day's `DateTime` is already available in scope and can be passed to the add-meal flow as `initialDate`.

### Meal-Slot Restructuring

This is the most involved change. Instead of rendering `events` as a flat list, the code would:
1. Group events by `mealType` within each day
2. Render sections for each `MealType` value
3. Show filled event tiles in their section
4. Show "+ Add [type]" placeholder for empty sections
5. The `MealType` enum already exists with `breakfast`, `lunch`, `dinner`, `snack` values and `displayName` getters

### State Management

The current approach uses `setState` directly in the `StatefulWidget`. This is adequate for the proposed changes since all the new interactions (FAB tap, per-day "+" tap, inline slot tap) ultimately open the same bottom sheet workflow. No state management migration is needed.

---

## Estimated Complexity

| Priority | Items | Total Effort | Risk |
|----------|-------|-------------|------|
| P0 | FAB + per-day buttons + quick add | 5-8 hours | Low -- follows existing patterns, API already supports it |
| P1 | Meal slots + empty states + today button | 6-9 hours | Low-Medium -- meal slot restructuring requires careful layout work |
| P2 | Recipe picker + tap options + month view | 13-20 hours | Medium -- recipe picker needs new widget; month view is significant UI work |
| P3 | Drag-drop + AI suggestions + recurring UI | 26-36 hours | High -- drag-drop in Flutter `ReorderableListView` or custom gesture handling is complex |

**Recommended implementation order:** P0 items first (can be done in a single sprint), then P1 items, then P2 items individually as capacity allows. P3 items should be evaluated after user feedback on P0+P1 improvements.

The P0 changes alone would fully address the user's reported pain point ("missing a '+' button somewhere") and transform the calendar from a passive display into an active planning tool.
