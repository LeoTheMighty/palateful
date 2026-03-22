# Story Import.5: Text Paste Import

Status: done

## Story

As a user,
I want to paste recipe text from any source (email, message, web page) and have AI structure it into a recipe,
so that I can save recipes without needing a URL or photo.

## Acceptance Criteria

1. "Paste Text" option in Add Recipe sheet navigates to a text paste screen
2. Text paste screen has a large text input area with a "Paste from Clipboard" button
3. Tapping "Extract Recipe" sends text to the import pipeline with source_type "text"
4. Extracted recipe goes through the standard import review flow (same review screen as URL/photo imports)
5. Works for single recipes (one recipe per paste)
6. Shows loading/progress state during AI extraction
7. Handles error states: empty text, text too long (>16K chars), extraction failure
8. Creates an Activity entry for the import (from Story 3)

## Tasks / Subtasks

- [x] Task 1: Backend — Text import source type (AC: #4)
  - [x] Verify `StartImport` endpoint accepts `source_type: "text"` with a `raw_text` field
  - [x] If not, add support: create ImportJob with source_type "text", create single ImportItem with raw_text as raw_data
  - [x] Route to `TextExtractor` (already exists at `libraries/utils/utils/services/recipe_extractors/text_extractor.py`)
  - [x] Ensure extraction → match ingredients → review pipeline works for text source

- [x] Task 2: Flutter — Text paste screen (AC: #1, #2, #3, #6, #7)
  - [x] Create `app/lib/features/recipes/add_recipe/text_paste_import_screen.dart`
  - [x] UI layout:
    - AppBar: "Paste Recipe"
    - Large `TextField` (multiline, maxLines: 15, hint: "Paste your recipe text here...")
    - "Paste from Clipboard" button (reads clipboard, fills field)
    - Character count indicator (max 16K)
    - "Extract Recipe" primary button (disabled if empty)
  - [x] On submit: call StartImport API with source_type "text"
  - [x] Show loading state with message "AI is reading your recipe..."
  - [x] On success: navigate to import review screen
  - [x] On error: show error message in snackbar

- [x] Task 3: Wire into Add Recipe sheet (AC: #1)
  - [x] Update Add Recipe sheet from Story 4 — replace "Coming soon" toast with actual navigation
  - [x] Route: `/recipes/add/text` → TextPasteImportScreen

- [x] Task 4: Add route (AC: #1)
  - [x] Add route for `/recipes/add/text` in `app/lib/core/router/app_router.dart`
  - [x] Pass `bookId` if available (from recipe book context)

- [x] Task 5: Activity integration (AC: #8)
  - [x] After successful import start: create activity "Importing recipe from pasted text..."
  - [x] After completion: create activity with result status

## Dev Notes

- `TextExtractor` at `libraries/utils/utils/services/recipe_extractors/text_extractor.py` already handles:
  - Raw text → GPT-4o-mini → structured recipe JSON
  - OCR error correction (also useful for messy pasted text)
  - 16K char truncation
  - Cost: ~$0.001-0.002 per extraction
- The import review screen already exists: `import_item_review_screen.dart`
- "Paste from Clipboard" uses `Clipboard.getData(Clipboard.kTextPlain)` from Flutter
- This is a high-value, low-effort feature — the backend already supports it

### References

- [Investigation: 06-import-flow-overhaul.md — Text Paste Import section]
- [Epic: epic-import-activity-nav.md]
