# Story iOS.6: Siri Shortcuts + Spotlight Search

Status: done

## Story

As a user,
I want to say "Hey Siri, what's for dinner?" or "Add milk to my shopping list" and have it just work,
so that I can interact with Palateful hands-free while cooking or on the go.

## Acceptance Criteria

1. Siri responds to "What's for dinner?" with the next dinner meal event
2. "Start cooking [recipe name]" opens cook mode for that recipe
3. "Add [item] to my shopping list" adds to the default shopping list
4. "How many items on my shopping list?" reads the count
5. "Start a [X] minute timer" starts a cooking timer (with Live Activity if available)
6. Recipes are indexed in Spotlight search — searching a recipe name in iOS search shows the Palateful result
7. Tapping a Spotlight result opens the recipe in Palateful
8. Shortcuts app shows Palateful actions for automation

## Tasks / Subtasks

- [x] Task 1: Define App Intents — native Swift (AC: #1, #2, #3, #4, #5, #8)
  - [x] Create Swift App Intent files in the main app target:
    - `WhatsForDinnerIntent` — queries meal events, returns speech response
    - `StartCookingIntent` — parameter: recipe name (entity), opens cook mode
    - `AddToShoppingListIntent` — parameters: item name, optional quantity/unit
    - `ShoppingListCountIntent` — returns count as speech
    - `StartTimerIntent` — parameter: minutes, optional label
  - [x] Each intent needs: title, description, parameter definitions, `perform()` method
  - [x] Register intents with `AppShortcutsProvider` for Shortcuts app visibility

- [x] Task 2: Intent data access (AC: #1, #2, #3, #4)
  - [x] Intents need to read app data — use shared UserDefaults (App Group) for:
    - Next meal: read `today_meals_json` (from widget data service)
    - Recipe list: read `recipes_index_json` (new — lightweight recipe name→ID mapping)
    - Shopping list: read `shopping_list_json` (from widget data service)
    - Default shopping list ID: read from UserDefaults
  - [x] For mutations (add to list): make API call from intent (reuse auth token from Story 5)

- [x] Task 3: Flutter — Donate user activities for Siri suggestions (AC: #8)
  - [x] When user starts cooking a recipe: donate `StartCookingIntent` activity
  - [x] When user views shopping list: donate `ShoppingListCountIntent` activity
  - [x] iOS uses donations to suggest shortcuts to the user
  - [x] Use platform channel to call native donation APIs

- [x] Task 4: Spotlight indexing (AC: #6, #7)
  - [x] Create `SpotlightIndexService` via platform channel
  - [x] When recipes are loaded: index each as `CSSearchableItem` with:
    - `uniqueIdentifier`: recipe ID
    - `title`: recipe name
    - `contentDescription`: first 100 chars of description or ingredient summary
    - `thumbnailData`: recipe photo (if available)
    - `keywords`: recipe tags, ingredient names
    - `domainIdentifier`: "com.palateful.recipes"
  - [x] Deep link: `palateful://recipes/{id}` → Flutter router handles opening
  - [x] Re-index when recipes change (add, edit, delete)
  - [x] Deindex when recipe is deleted

- [x] Task 5: Flutter — Write recipe index for intents (AC: #2)
  - [x] Write lightweight recipe index to UserDefaults via `home_widget`:
    - Key: `recipes_index_json`
    - Value: array of `{id, name, book_name}` for intent entity resolution
  - [x] Update on recipe load, add, edit, delete

## Dev Notes

- App Intents framework is native Swift only — Flutter packages for this are limited
- `perform()` methods run in the app process (foreground intents) or extension process
- For "Start cooking" intent: needs a way to resolve recipe name to ID. Entity resolution via the recipes index
- Siri Shortcuts appear automatically in the Shortcuts app once intents are registered with `AppShortcutsProvider`
- Spotlight indexing via `CSSearchableItem` requires `CoreSpotlight` framework
- Keep the recipe index small — only name and ID, not full recipe data
- Test Siri on device — simulator has limited Siri support

### References

- [Investigation: 09-ios-native-features.md — Siri & Shortcuts section]
- [Epic: epic-ios-native.md]
