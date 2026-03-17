# Story 3.2: OCR Photo Import

Status: done

## Story

As a user,
I want to photograph a physical recipe and have it converted to structured data,
so that I can digitize handwritten or printed recipes from cookbooks and cards.

## Acceptance Criteria

1. User can take a photo or select from gallery and choose a destination book
2. Image is sent to the OCR pipeline (HunyuanOCR via AWS Batch)
3. OCR text is structured into recipe data (ingredients, steps, title) via AI
4. User sees a preview of the extracted recipe before saving
5. User can approve the import to create the recipe
6. OCR completes within 60 seconds per image
7. Source attribution includes "photo import" reference

## Tasks / Subtasks

- [x] Task 1: Add `extract_recipe_from_text` AI function (AC: #3)
  - [x] Create text extraction prompt (different from HTML prompt)
  - [x] Add `extract_recipe_from_text()` to recipe_extractors module
  - [x] Handles OCR text (possibly noisy) → structured recipe JSON

- [x] Task 2: Add `source_type="photo"` to StartImport (AC: #1, #2)
  - [x] Accept `ocr_texts: list[str]` parameter in StartImport.Params
  - [x] Create ImportItems with `source_type="photo"` and `raw_data={"text": ocr_text}`
  - [x] Dispatch processing

- [x] Task 3: Handle photo items in import tasks (AC: #3)
  - [x] ParseSourceTask: handle photo source type (items pre-created by StartImport)
  - [x] ExtractRecipeTask: when source_type=="photo", use `extract_recipe_from_text` on raw_data text

- [x] Task 4: Add backend tests (AC: #2, #3)
  - [x] Test StartImport with source_type="photo" (success + empty texts)
  - [ ] Test extract_recipe_from_text function (requires OpenAI mock — deferred)

- [x] Task 5: Modify PhotoCaptureScreen for import flow (AC: #1, #4, #5, #6, #7)
  - [x] Add book selector dropdown
  - [x] After OCR succeeds, call startImport with extracted texts
  - [x] Poll import job for status
  - [x] Show structured recipe preview (reuse pattern from UrlImportScreen)
  - [x] Approve/skip buttons
  - [x] Handle multi-image: concatenate OCR texts into single recipe

## Code Review Action Items

- [x] [HIGH] Add `Field(max_length=10)` to `ocr_texts` in StartImport.Params — unbounded list size [start_import.py:155]
- [x] [HIGH] Fix `ParseSourceTask` double-write of `total_items` for photo imports — use `job.total_items` directly instead of re-querying [parse_source_task.py:54]
- [x] [MEDIUM] Add OCR polling timeout (60 polls = 5 minutes) to prevent infinite polling [photo_capture_screen.dart:262]
- [x] [MEDIUM] Add `mounted` check before calling `_startImportPipeline` from timer callback [photo_capture_screen.dart:292]
- [ ] [MEDIUM] `BatchParserService` is now orphaned dead code after PhotoCaptureScreen rewrite — cleanup in future story
- [x] [LOW] Update story tasks to `[x]` to reflect completed work

## Dev Notes

### Architecture

The photo import bridges two existing pipelines:
1. **Parser pipeline** (exists): Image → S3 → AWS Batch OCR → raw text
2. **Import pipeline** (exists): Source → AI structuring → structured recipe → review → approve

For Story 3.2, Flutter orchestrates the OCR step (existing), then feeds the extracted text into the import pipeline with `source_type="photo"`.

### Flow

1. User takes photo(s) → uploads to S3 → submits parser job(s) → polls for OCR text
2. When OCR completes, Flutter calls `POST /recipe-books/{bookId}/import` with `source_type="photo"` + `ocr_texts=[text1, text2, ...]`
3. Backend creates ImportJob + ImportItem(s) with raw_data containing OCR text
4. ExtractRecipeTask AI-structures text → parsed_recipe
5. Flutter polls import job → shows preview → user approves

### Multi-image handling

Multiple photos of the same recipe (e.g., front and back of a card) should concatenate their OCR texts into a single import item. Each separate recipe should be a separate import item.
For simplicity in this story: all selected images = one recipe (texts concatenated).

### DO NOT:
- Implement edit-before-approve (Story 3.4)
- Add bulk photo import (separate story)
- Modify existing parser pipeline endpoints
