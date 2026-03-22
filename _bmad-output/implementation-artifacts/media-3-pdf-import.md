# Story Media.3: PDF Import — Text + OCR Dual Path

Status: done

## Story

As a user,
I want to import recipes from PDF files — whether they're text-based blog exports or scanned cookbook pages,
so that I can digitize my cookbook collection and save PDF recipes from the web.

## Acceptance Criteria

1. PDF import option available in Add Recipe sheet under "More Options"
2. File picker accepts `.pdf` files
3. Text-based PDFs: text extracted via PyMuPDF (free, fast)
4. Scanned/image PDFs: pages converted to images and processed via existing OCR pipeline
5. Multi-recipe PDFs: AI detects recipe boundaries and creates one ImportItem per recipe
6. Single-recipe PDFs: processed as one import item
7. Book picker shown before processing (bulk = ask explicitly, pre-select default)
8. Progress tracked in Activity feed
9. Circuit breaker: if first 3 pages yield no recipe content, ask "Is this a recipe PDF?"
10. File size limit: 50MB max, 100 pages max

## Tasks / Subtasks

- [x] Task 1: Backend — PDF extractor (AC: #3, #4)
  - [x] Create `libraries/utils/utils/services/recipe_extractors/pdf_extractor.py`
  - [x] `PDFExtractor.classify(file_path)` → determine if text-based or scanned
    - Text-based: PyMuPDF text extraction yields >100 chars/page average
    - Scanned: minimal text, primarily images
  - [x] `PDFExtractor.extract_text(file_path)` → PyMuPDF text extraction for text-based PDFs
  - [x] `PDFExtractor.extract_pages_as_images(file_path)` → render each page to image for scanned PDFs
  - [x] Add `pymupdf` to worker service dependencies

- [x] Task 2: Backend — Recipe boundary detection (AC: #5, #6)
  - [x] For text-based PDFs: send extracted text to GPT-4o-mini with prompt:
    "This is text from a PDF. Identify where each recipe begins and ends. Return a list of recipe boundaries (start line, end line, recipe title)."
  - [x] For single-page or clearly single-recipe PDFs: skip boundary detection
  - [x] Create one ImportItem per detected recipe
  - [x] Each item's raw_data contains the text for that specific recipe

- [x] Task 3: Backend — PDF import endpoint + pipeline integration (AC: #8)
  - [x] Accept PDF uploads via existing `POST /recipe-books/{book_id}/import/file` endpoint
  - [x] Detect `file_type: "pdf"` → route to PDF extractor
  - [x] Classify → extract text or images → detect boundaries → create ImportItems → standard pipeline
  - [x] For scanned pages: send images through existing photo/OCR pipeline (HunyuanOCR → TextExtractor)
  - [x] Create activity entries for progress

- [x] Task 4: Backend — Circuit breaker (AC: #9, #10)
  - [x] Enforce limits: reject files >50MB, >100 pages
  - [x] After processing first 3 pages: if no recipe content detected, pause and ask user
  - [x] Similar pattern to spreadsheet circuit breaker

- [x] Task 5: Flutter — PDF import screen (AC: #1, #2, #7)
  - [x] Create `app/lib/features/recipes/add_recipe/pdf_import_screen.dart`
  - [x] File picker filtered for `.pdf`
  - [x] Show book picker after file selected (pre-select default)
  - [x] Processing screen with progress: "Reading PDF..." → "Detecting recipes..." → "Extracting X recipes..."
  - [x] Results: summary + review for flagged items

- [x] Task 6: Flutter — Circuit breaker UI (AC: #9)
  - [x] Same pattern as spreadsheet circuit breaker
  - [x] "This doesn't look like a recipe PDF. Continue anyway?"

## Dev Notes

- PyMuPDF (`pymupdf` / `fitz`) is lightweight, C-based, fast. Handles text extraction AND page-to-image rendering
- For scanned PDFs, each page becomes an image → existing HunyuanOCR pipeline handles it
- Recipe boundary detection is the hardest sub-problem. Start with AI detection, fall back to one-recipe-per-page
- Full cookbook PDFs (50+ recipes, scanned) should be treated as batch jobs — could take 5-30 minutes
- Cost: text-based single recipe ~$0.003, scanned single recipe ~$0.006, full scanned cookbook (50 recipes) ~$0.30
- Large batch imports show progress in Activity feed, not blocking the UI

### References

- [Investigation: 11-universal-media-import.md — PDF section]
- [Epic: epic-media-import.md]
