# Story Import.4: Import Quick Wins — URL, Onboarding, Empty States

Status: done

## Story

As a user,
I want import options to be discoverable at every natural touchpoint,
so that I can easily import recipes whether I'm onboarding, browsing an empty book, or tapping the add button.

## Acceptance Criteria

1. Add Recipe bottom sheet shows 4 options: URL, Photo, Paste Text (placeholder), Spreadsheet (placeholder), Manual — grouped as "Quick Import" and "More Options"
2. URL option navigates to existing `url_import_screen`
3. Onboarding "Import From Existing Source" routes to the Add Recipe sheet after completing onboarding
4. Empty recipe book state shows actionable import CTAs: "Import from URL", "Take a Photo", "Create Manually"
5. Paste Text and Spreadsheet options show "Coming soon" toast (implemented in Stories 5 and 7)

## Tasks / Subtasks

- [x] Task 1: Redesign Add Recipe bottom sheet (AC: #1, #2, #5)
  - [x] Modify `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart`
  - [x] Restructure to grouped layout:
    - **Quick Import** section header
      - From URL — "Paste a recipe link"
      - From Photo — "Snap or upload a photo"
      - Paste Text — "Paste recipe from anywhere" (toast: "Coming soon" for now)
    - **More Options** section header
      - From Spreadsheet — "Import CSV or Excel file" (toast: "Coming soon" for now)
      - Create Manually — "Build from scratch"
  - [x] URL option routes to existing `/recipes/add/url` screen
  - [x] Remove the old "Files" stub option

- [x] Task 2: Fix onboarding import routing (AC: #3)
  - [x] Modify `app/lib/features/onboarding/onboarding_start_screen.dart`
  - [x] When user selects "Import From Existing Source":
    - Call `completeOnboarding(startMethod: 'import')` (existing)
    - Navigate to home (existing)
    - Then show the Add Recipe sheet automatically
  - [x] Ensure the import flow lands in the user's default recipe book

- [x] Task 3: Improve empty recipe book state (AC: #4)
  - [x] Find the empty state widget used in recipe book detail screen
  - [x] Replace passive "Tap + to add a recipe" with actionable buttons:
    - "Import from URL" → navigates to URL import with book pre-selected
    - "Take a Photo" → navigates to photo capture with book pre-selected
    - "Create Manually" → navigates to recipe wizard with book pre-selected
  - [x] Style as a centered card with stacked action buttons

## Dev Notes

- The current Add Recipe sheet has 3 `ListTile` options at `add_recipe_sheet.dart:45-73`
- The URL import screen already exists and works — just needs to be reachable from the sheet
- Onboarding: `onboarding_start_screen.dart:140-159` — all three methods just call `completeOnboarding()`
- Pass the `bookId` context through to import screens so recipes land in the right book
- "Coming soon" toasts for Paste Text and Spreadsheet are temporary — Stories 5 and 7 replace them

### References

- [Investigation: 06-import-flow-overhaul.md — Entry Points section]
- [Epic: epic-import-activity-nav.md]
