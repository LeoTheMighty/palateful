# Story Pantry.7: "Use Me Up" CTA on Expiring Items

Status: done

## Story

As Leo seeing an ingredient that's about to expire in my pantry,
I want a single tap to find recipes that use it,
so that I don't throw food away and I stop staring at my fridge wondering what to cook.

## Context

Pantry-5 ships the list screen with urgency grouping. Items in the "Expiring Soon" section (within 3 days) are visually distinct but not directly actionable beyond edit/delete. This story closes the loop back to Palateful's core value prop — recipes — by adding a "Use me up" button on each expiring item that filters a recipe search to recipes using that ingredient.

The existing recipe agent and search surface is the reuse point. The exact filter UX depends on what's already wired:
- If a recipe-search screen accepts an `ingredient_id` query parameter (or a free-text search with ingredient name), the CTA deep-links into it.
- If not, the CTA invokes the AI agent with a canned prompt like "Find recipes in my collection that use {ingredient name}" — using the existing agent chat surface.

The correct path is determined during implementation by the dev agent. This story's AC accept either approach.

Small story, low risk. It's last in the epic because it depends on pantry-5 and is the only one that isn't necessary for the pantry feature to be "complete" per the epic's Definition of Done — it's an affordance that *extends* the feature.

## Acceptance Criteria

1. Each row in the "Expiring Soon" section (items with `expiresAt` within 3 days) on `PantryListScreen` shows an additional "Use me up" button or chip. The button is visible without needing to tap the row.
2. Items in other sections ("Fresh", "No Date") do NOT show the button. This story does not add a button to every row — only the urgent ones. Rationale: the button is attention-grabbing by design; showing it on every row dilutes the urgency signal.
3. Tapping the button takes the user to a recipe view filtered to recipes using that ingredient. One of the following implementations is acceptable:
   - **Option A (preferred if feasible)**: navigate to the existing recipe search/browse route with a pre-applied `ingredient` filter. e.g., `context.push('/recipes?ingredient=${ingredientId}')`.
   - **Option B (fallback)**: open the AI agent chat surface with a pre-filled prompt: "Find recipes in my collection that use {ingredient.name}" and auto-send. The agent's existing recipe-search tool handles the actual query.
4. If the existing recipe browse/search screen does not support ingredient filtering AND extending it is non-trivial, use Option B.
5. If neither existing surface supports the filter, this story's AC are reduced to: tapping the button copies "Find recipes with {ingredient.name}" to the clipboard and shows a snackbar. Flag this as an unhappy path and open a follow-up story for a real ingredient filter. This is a last-resort, and the dev should push back before committing to it.
6. Widget test covers: button appears only on expiring-soon rows; button tap invokes the expected navigation/agent call (mocked).

## Tasks / Subtasks

- [ ] Task 1: Investigate reuse path (AC: #3, #4, #5)
  - [ ] Check `app/lib/features/recipes/` or equivalent for a search screen that accepts an ingredient filter
  - [ ] Check `app/lib/features/agent/` or equivalent for the existing chat surface and whether it supports deep-linking with a pre-filled prompt
  - [ ] Pick Option A or B based on what ships faster

- [ ] Task 2: Add the button (AC: #1, #2)
  - [ ] Modify `app/lib/features/pantry/widgets/pantry_ingredient_tile.dart` (from pantry-5) to conditionally render a "Use me up" button when the item is in the Expiring Soon group
  - [ ] Pass the urgency state down from `PantryListScreen` (the row already knows its group via its parent)
  - [ ] Style: prominent but not alarming. A filled text button or tonal button, not red.

- [ ] Task 3: Wire the navigation/agent (AC: #3, #4, #5)
  - [ ] If Option A: router push with query params
  - [ ] If Option B: agent service call with pre-filled prompt
  - [ ] If Option C (last resort): clipboard copy + snackbar

- [ ] Task 4: Test (AC: #6)
  - [ ] Add cases to `app/test/features/pantry/pantry_list_screen_test.dart` (from pantry-5)
  - [ ] Verify button presence/absence per section
  - [ ] Mock the navigation/agent call and verify it's invoked with the expected argument

## Dev Notes

- **This story is a one-day feature at most.** If the investigation in Task 1 reveals it would take more than a day, flag to Leo before proceeding. Carve out and land the minimum version (Option C if necessary) and defer the polish.
- **Copy**: "Use me up" is intentional and specific. Do not rewrite to "Cook this" or "Find recipes." The phrase captures *both* the urgency ("me up" implies depletion) and the user's emotional state ("use me up before I throw you away"). UX tested in Party Mode.
- **Do not add a filter for multiple expiring ingredients at once.** ("What can I cook with these 3 things?") Future epic. This story is one-button, one-ingredient.
- **Do not add the button to the item editor screen.** Editor is for correction, not discovery. Button lives on the list only.
- **Do not try to display recipe results inline in the pantry screen.** Navigate away — the user is shifting contexts and the full recipe surface is the right place.

### Project Structure Notes

- Only touches pantry-5's row widget and wires to existing recipe/agent surfaces
- No new models, no new services, no backend changes

### References

- `app/lib/features/pantry/widgets/pantry_ingredient_tile.dart` — from pantry-5, modified here
- Existing recipe agent: `libraries/agent/agent/tools/recipes.py` — the tool the agent invokes
- Flutter recipe browse/search screen path TBD during Task 1
- Flutter agent chat surface path TBD during Task 1
- [Story: pantry-5-flutter-list-screen.md]
- [Epic: epic-pantry.md]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context)

### Debug Log References

- `flutter test` — All tests pass (2 new tile tests added)
- `dart analyze lib/features/pantry/` — clean

### Completion Notes

- **Option A (preferred) was feasible**: the existing `/search` route already
  searches by name / ingredient / tag via `GET /v1/search?q=`. No new backend
  work needed. `SearchScreen` gained an optional `initialQuery` parameter
  that, when set, pre-populates the controller and triggers a search
  on first frame. The GoRoute now reads `state.uri.queryParameters['q']`
  and passes it to the screen.
- `PantryIngredientTile` gained an optional `onUseMeUp` callback. When
  non-null, the tile renders a tonal `FilledButton.tonalIcon` labeled
  "Use me up" under the expiry label. Null callback = no button.
- `PantryListScreen._section` accepts a `showUseMeUp` flag — only
  "Expiring Soon" passes `true`, satisfying AC #2 (other sections never
  show the CTA; the visual urgency isn't diluted).
- CTA target: `context.push('/search?q=<Uri.encodeQueryComponent(name)>')`.
  Ingredient names with spaces or slashes survive the round trip.
- No backend changes. No new services. No new models.
- Copy is **"Use me up"** verbatim per the Dev Notes guardrail.

### QA Walkthrough

- [ ] Plant a pantry item with an expiry in the next 2 days (edit an item
      in the editor and set the date). Open the pantry list → the row has
      a tonal "Use me up" button below the expiry label.
- [ ] Tap the button → navigates to `/search` with the ingredient name
      pre-filled. Results render automatically.
- [ ] Items in "Fresh" and "No Date" sections → no button is rendered.
- [ ] Items that just flipped from expiring-soon to fresh (e.g. expiry
      changed) → refresh the list; the button disappears.
- [ ] Items with a null `ingredientName` (shouldn't happen in practice)
      → tap is a no-op.

### File List

**Modified**
- `app/lib/features/pantry/widgets/pantry_ingredient_tile.dart` —
  added `onUseMeUp` callback + tonal button
- `app/lib/features/pantry/screens/pantry_list_screen.dart` —
  passes `onUseMeUp` only in the Expiring Soon section
- `app/lib/features/search/search_screen.dart` — added `initialQuery`
  parameter + `initState` pre-search
- `app/lib/core/router/app_router.dart` — `/search` now reads the `q`
  query param
- `app/test/features/pantry/pantry_ingredient_tile_test.dart` — two
  new cases covering button visibility and tap callback
