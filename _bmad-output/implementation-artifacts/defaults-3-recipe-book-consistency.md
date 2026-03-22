# Story Defaults.3: Default Recipe Book — Consistency Pass

Status: complete

## Story

As a user,
I want saving/importing a single recipe to go straight to my default recipe book,
so that the experience is consistent with shopping list defaults and I don't face unnecessary pickers.

## Acceptance Criteria

1. "Save Recipe" (single) → saves to default book instantly + snackbar "Saved to [Book Name] · Change"
2. Bulk import (spreadsheet, multi-URL) → opens book picker with default pre-selected
3. Same "Change" bottom sheet pattern as shopping lists (one-time redirect OR switch default)
4. Books tab shows star/pin badge on default book
5. Long-press any book card → "Set as default" option
6. `previous_recipe_book_id` added to users table for auto-recovery consistency
7. Creating a new recipe book auto-sets as default + toast notification

## Tasks / Subtasks

- [x] Task 1: Add previous_recipe_book_id to backend (AC: #6)
  - [x] Migration adding `previous_recipe_book_id` UUID FK to users table (nullable, ON DELETE SET NULL)
  - [x] Update User model
  - [x] Update GET /me to include it
  - [x] Update default-setting logic to shift old → previous

- [x] Task 2: Apply default pattern to "Save Recipe" flows (AC: #1)
  - [x] Find all single-recipe save/import flows in Flutter
  - [x] If default set → skip book picker, save to default, show snackbar with "Change"
  - [x] If no default → show picker, set chosen as default

- [x] Task 3: Apply bulk pattern to import flows (AC: #2)
  - [x] URL bulk import, spreadsheet import, any multi-recipe flow
  - [x] Show book picker with default pre-selected
  - [x] One confirm tap if default is correct

- [x] Task 4: Reuse "Change" bottom sheet from Defaults.2 (AC: #3)
  - [x] Adapt the `DefaultChangeSheet` widget to work for recipe books too
  - [x] Or make it generic: `DefaultChangeSheet<T>` with type parameter

- [x] Task 5: Default badge on Books tab (AC: #4)
  - [x] Same star/pin pattern as shopping list cards

- [x] Task 6: Long-press "Set as default" on book cards (AC: #5)
  - [x] Same pattern as shopping list long-press

- [x] Task 7: Auto-set on creation (AC: #7)
  - [x] New recipe book created → auto-set as default if user's first, or always
  - [x] Toast: "This is now your default recipe book"

## Dev Notes

- `default_recipe_book_id` already exists on users table — just need to ensure the frontend actually USES it for skip-picker behavior
- The `DefaultChangeSheet` from Story 2 should be made generic enough to reuse here
- This story ensures recipe books and shopping lists have identical default UX
- The "silent for singles, explicit for bulk" rule is key: single save = auto, import batch = ask

### References

- [Investigation: 05-shopping-list-default-cart.md — existing pattern section]
- [Epic: epic-smart-defaults.md]
