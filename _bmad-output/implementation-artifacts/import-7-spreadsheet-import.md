# Story Import.7: Spreadsheet Import — AI-Powered CSV/XLSX

Status: done

## Story

As a user,
I want to import recipes from a CSV or Excel spreadsheet by simply selecting the file and letting AI parse each row,
so that I can bulk-import mom's recipe spreadsheet without any manual column mapping.

## Acceptance Criteria

1. "From Spreadsheet" option in Add Recipe sheet opens a file picker for CSV and XLSX files
2. After selecting a file, a processing screen shows recipes appearing as they're parsed by AI
3. Each spreadsheet row is sent to the LLM with its column headers as context — NO column mapping UI
4. High-confidence results (name + ingredients + instructions parsed) auto-approve
5. Medium-confidence results (missing instructions) show for review with yellow flag
6. Low-confidence results (can't determine recipe name) are flagged as "Needs your input" with red indicator
7. Results summary screen: "✅ 47 recipes imported, ⚠️ 3 need review" with tap to review
8. Circuit breaker: if first 5 rows all return low confidence, pause and ask "Is this the right file?"
9. Progress tracked in Activity feed (from Story 6)
10. File size limits: 5MB for CSV, 10MB for XLSX, max 200 recipes
11. Destination book picker shown before import (bulk = ask explicitly, pre-select default)

## Tasks / Subtasks

- [x] Task 1: Backend — Spreadsheet parser (AC: #3, #10)
  - [x] Create spreadsheet parser utility (use `pandas` or `openpyxl` for XLSX, `csv` stdlib for CSV)
  - [x] Parse file → extract headers + rows
  - [x] For each row: create a dict with `{header: value}` pairs
  - [x] Serialize each row dict to text: "Column1: Value1\nColumn2: Value2\n..."
  - [x] Feed into `TextExtractor` (existing) — LLM parses semantic meaning from headers naturally
  - [x] Enforce limits: skip empty rows, cap at 200 recipes, validate file size

- [x] Task 2: Backend — Spreadsheet import endpoint (AC: #3, #9)
  - [x] New endpoint: `POST /recipe-books/{book_id}/import/file` accepting multipart file upload
  - [x] Upload file to S3 (or parse in-memory for small files)
  - [x] Create ImportJob with `source_type: "spreadsheet"`
  - [x] Create ImportItem per non-empty row
  - [x] Kick off extraction tasks in batches of 10 (existing pattern)
  - [x] Create Activity entries for progress

- [x] Task 3: Backend — Confidence scoring (AC: #4, #5, #6)
  - [x] After `TextExtractor` returns structured recipe:
    - **High**: has name AND ≥2 ingredients AND ≥1 instruction step → auto-approve
    - **Medium**: has name AND (ingredients OR instructions, not both) → flag for review
    - **Low**: missing name OR <2 total fields parsed → flag as "Needs input"
  - [x] Store confidence level on ImportItem (add field or use metadata)
  - [x] Auto-approve high-confidence items (create recipe directly, skip review)

- [x] Task 4: Backend — Circuit breaker (AC: #8)
  - [x] After first 5 ImportItems are extracted: check confidence scores
  - [x] If all 5 are low-confidence: pause the import job, set status to "needs_confirmation"
  - [x] Return column headers in the response so frontend can show "we found these columns: [X, Y, Z]"
  - [x] User can confirm to continue or cancel

- [x] Task 5: Flutter — File picker + processing screen (AC: #1, #2, #11)
  - [x] Update Add Recipe sheet — replace "Coming soon" toast with actual navigation
  - [x] File picker using `file_picker` package: filter for `.csv`, `.xlsx`, `.xls`
  - [x] After file selected: show book picker (pre-select default book)
  - [x] Processing screen:
    - Progress bar: "Processing 50 recipes... 32/50"
    - Recipe cards appearing as they're parsed (stream/poll from API)
    - Each card shows: recipe name, confidence badge (green/yellow/red), ingredient count
  - [x] Poll import job status at 2-second intervals

- [x] Task 6: Flutter — Results + review screen (AC: #7)
  - [x] Results summary at top: "✅ 47 imported, ⚠️ 3 need review"
  - [x] List of flagged items with tap to edit (reuse `import_item_review_screen.dart`)
  - [x] "Done" button returns to recipe book

- [x] Task 7: Flutter — Circuit breaker UI (AC: #8)
  - [x] If import job status is "needs_confirmation":
    - Show message: "We're having trouble finding recipes. Columns found: [X, Y, Z]"
    - "Continue Anyway" button → resumes import
    - "Cancel" button → cancels import job
    - "Pick Different File" button → returns to file picker

## Dev Notes

- **No column mapping.** This is the key architectural decision. Each row is serialized with its headers and sent to the LLM as unstructured text. The LLM naturally understands "Ingredients: 1lb beef, 2 cups rice" without being told "column 3 = ingredients."
- Cost: ~$0.001-0.002 per row via GPT-4o-mini. 200 recipes ≈ $0.20-0.40.
- `TextExtractor` already handles messy text → structured recipe. It was built for OCR output which is often noisier than spreadsheet data.
- Batching in groups of 10 is the existing pattern in `parse_source_task.py`.
- The `file_picker` package handles iOS file selection including iCloud Drive.
- XLSX parsing: `openpyxl` is pure Python, no system dependencies. Add to poetry if not present.
- Existing `ImportJob` model already has `source_type` enum that can include "spreadsheet".

### References

- [Investigation: 06-import-flow-overhaul.md — Spreadsheet Import Architecture section]
- [Epic: epic-import-activity-nav.md]
