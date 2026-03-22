# Story Defaults.5: Auto-Recovery & Context Switching

Status: complete

## Story

As a user,
I want my default to automatically switch back to my previous list/book when I complete or archive a temporary one,
so that I don't have to remember to manually change it back after a road trip or event.

## Acceptance Criteria

1. When a shopping list that is the user's default is marked as completed → auto-restore `previous_shopping_list_id` as the new default
2. When a recipe book that is the user's default is deleted → auto-restore `previous_recipe_book_id` as the new default
3. Auto-recovery shows a celebratory toast: "Your default is now [Previous Name] again"
4. If no previous default exists, clear the default and show: "No default list set — pick one from Cart tab"
5. When manually setting a new default, the current default moves to `previous_*` field
6. The `previous_*` field is one-deep only — no stack history beyond that

## Tasks / Subtasks

- [x] Task 1: Backend auto-recovery for shopping lists (AC: #1, #4, #5)
  - [x] In the shopping list completion/archive handler: if the completed list is the user's default
    - [x] Set `default_shopping_list_id` = `previous_shopping_list_id`
    - [x] Clear `previous_shopping_list_id`
  - [x] In the delete handler: same logic (ON DELETE SET NULL handles the FK, but previous restoration needs explicit logic)
  - [x] Return the new default in the response so frontend can show the toast

- [x] Task 2: Backend auto-recovery for recipe books (AC: #2, #5)
  - [x] Same pattern as Task 1 for recipe book deletion
  - [x] Recipe books don't have a "complete" state, so only triggers on delete

- [x] Task 3: Frontend auto-recovery UX (AC: #3, #4)
  - [x] After completing/archiving a shopping list, check if it was the default
  - [x] If auto-recovered: show toast "Your default is now [Name] again"
  - [x] If no previous: show toast "No default list set — pick one from Cart tab"
  - [x] Same pattern for recipe book deletion

- [x] Task 4: Ensure "set default" always shifts to previous (AC: #5, #6)
  - [x] Verify the PUT endpoint from Story 1 correctly moves current → previous
  - [x] Verify it only tracks one-deep (setting a new default overwrites previous, doesn't stack)

## Dev Notes

- This is the "pop back" pattern from the party mode discussion
- One-deep only — users think in "my normal" and "my right now", not a full stack
- The backend should handle the swap atomically in the same transaction
- ON DELETE SET NULL handles FK cleanup, but the previous→default promotion needs explicit code
- Depends on Stories 1 and 3 for the `previous_*` columns

### References

- [Epic: epic-smart-defaults.md — Design Principles #3: One-deep recovery]
