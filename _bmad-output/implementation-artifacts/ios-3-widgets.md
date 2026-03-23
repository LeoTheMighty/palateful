# Story iOS.3: Home Screen & Lock Screen Widgets — Next Meal + Shopping List

Status: done

## Story

As a user,
I want to see my next meal and shopping list on my home screen and lock screen,
so that I can glance at what's cooking and what I need to buy without opening the app.

## Acceptance Criteria

1. **"Next Meal" widget** available in small (recipe name + time) and medium (all today's meals) sizes
2. **"Shopping List" widget** available in small (item count) and medium (top 5 items + count) sizes
3. Lock screen widgets: "Next Meal" circular (meal icon + time) and rectangular (meal name + time)
4. Lock screen widgets: "Shopping Count" circular (cart icon + count)
5. Tapping any widget opens the app to the relevant screen (recipe detail, calendar, shopping list)
6. Widgets update when meals are planned/changed or shopping items are added/checked
7. StandBy mode works automatically with home screen widgets (zero extra code)
8. Widgets use Palateful's color palette (cream, chocolate, terracotta, hazelnut)
9. Widgets show appropriate empty states ("No meals planned", "Shopping list empty")
10. Data refreshes via `WidgetCenter.shared.reloadAllTimelines()` when Flutter app updates relevant data

## Tasks / Subtasks

- [x] Task 1: Flutter — Widget data provider (AC: #6, #10)
  - [x] Create `app/lib/services/widget_data_service.dart`
  - [x] Methods to write data to shared UserDefaults via `home_widget`:
    - `updateNextMealWidget(mealEvent)` → writes `next_meal_json`
    - `updateTodayMealsWidget(meals)` → writes `today_meals_json`
    - `updateShoppingListWidget(list, items)` → writes `shopping_list_json`
  - [x] Call update methods when:
    - Meal events are created/updated/deleted
    - Shopping list items are added/checked/removed
    - App enters background (`didChangeAppLifecycleState`)
  - [x] Call `HomeWidget.updateWidget()` after each data write to trigger timeline reload

- [x] Task 2: SwiftUI — Next Meal widget (AC: #1, #8, #9)
  - [x] In Widget Extension: create `NextMealWidget`
  - [x] **Small size**: meal type icon (🍳/🥗/🍝 based on type), recipe name (truncated), time
  - [x] **Medium size**: list of today's meals — each row: time, meal type badge, recipe name
  - [x] Read from `UserDefaults(suiteName: "group.com.palateful.app")` key `next_meal_json` / `today_meals_json`
  - [x] Empty state: "No meals planned" with calendar icon
  - [x] Use Palateful colors: cream background, chocolate text, terracotta accents
  - [x] Timeline: reload every 30 minutes + on data change

- [x] Task 3: SwiftUI — Shopping List widget (AC: #2, #8, #9)
  - [x] Create `ShoppingListWidget`
  - [x] **Small size**: cart icon + "X items" count badge
  - [x] **Medium size**: top 5 unchecked items as list, total count at bottom
  - [x] Read from `shopping_list_json` UserDefaults key
  - [x] Empty state: "List empty ✓" with checkmark
  - [x] Items show name + quantity (e.g., "Milk — 1 gal")
  - [x] Use Palateful colors matching the app

- [x] Task 4: SwiftUI — Lock screen widgets (AC: #3, #4)
  - [x] `NextMealLockWidget` — WidgetFamily `.accessoryCircular` and `.accessoryRectangular`
  - [x] Circular: meal type SF Symbol + time (e.g., dinner fork icon + "6:30")
  - [x] Rectangular: "Dinner at 6:30 PM" + recipe name (2 lines)
  - [x] `ShoppingCountLockWidget` — WidgetFamily `.accessoryCircular`
  - [x] Circular: cart SF Symbol + item count number

- [x] Task 5: Deep link handling (AC: #5)
  - [x] Each widget specifies a `widgetURL` for tap handling:
    - Next Meal small → `palateful://calendar`
    - Next Meal medium (tapping a meal) → `palateful://recipes/{id}`
    - Shopping List → `palateful://cart/{listId}`
  - [x] Ensure Flutter router handles these deep links

- [x] Task 6: Widget gallery configuration (AC: #1, #2, #3, #4)
  - [x] Configure `WidgetBundle` with all widget types
  - [x] Add widget descriptions and preview snapshots for the gallery
  - [x] Add widget display names: "Next Meal", "Today's Meals", "Shopping List", "Shopping Count"

## Dev Notes

- All widget UI is SwiftUI — cannot use Flutter widgets
- `@available(iOS 16.0, *)` for lock screen widgets (WidgetFamily `.accessoryCircular`, `.accessoryRectangular`)
- StandBy mode (iOS 17) works automatically — no extra code needed
- Timeline providers should use `.atEnd` policy for meal widgets (reload after the meal time passes)
- Shopping list widget should use `.after(Date().addingTimeInterval(1800))` for 30-min refresh
- Keep the JSON payloads in UserDefaults small — only essential display data, not full models
- SF Symbols for meal types: `fork.knife` (dinner), `cup.and.saucer` (breakfast), `leaf` (lunch), `birthday.cake` (snack)

### References

- [Investigation: 09-ios-native-features.md — Widget section + Widget Family Matrix]
- [Epic: epic-ios-native.md]
