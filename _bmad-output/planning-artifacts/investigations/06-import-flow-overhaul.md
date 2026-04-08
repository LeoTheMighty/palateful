# Investigation: Recipe Import Flow Overhaul

## Executive Summary

The Palateful app has a functional but fragmented import system. URL import (single and bulk) works end-to-end through a backend pipeline (JSON-LD extraction with AI fallback), photo/OCR import works via a separate parser service, and manual entry uses a step wizard. However, there are critical gaps: **file/spreadsheet import is completely unimplemented** (the screen is a "Coming soon" stub), there is **no text paste import**, **no support for standard recipe exchange formats**, and **the onboarding "Import From Existing Source" option does not actually route to any import flow** -- it just completes onboarding and drops the user at the home screen. The "Add Recipe" bottom sheet offers only 3 options (Photo, Files, Manual), **missing the URL import entirely** from the primary entry point. Import from share sheet works well for URLs but cannot handle files. Bulk import only supports URLs, not spreadsheets or other bulk formats.

The core pain point -- "mom shared her spreadsheet and I want to add all those recipes" -- is completely unsupported today.

---

## Current State Analysis

### Import Entry Points

| Entry Point | Location | What It Does | Status |
|---|---|---|---|
| **Add Recipe sheet** | FAB on home/recipe book screens | Shows: Photo, Files, Manual | **Missing URL import option** |
| **Recipe Book detail menu** | Overflow menu in recipe book | Import URL, Import Photo, Bulk Import (URLs) | Working |
| **Share sheet (iOS)** | `ReceiveSharingIntent` in `main.dart` | Handles shared URLs via `ShareImportScreen` | Working for URLs only |
| **Onboarding** | "Import From Existing Source" card | Calls `completeOnboarding(startMethod: 'import')` then goes to home | **Does not route to any import flow** |
| **Empty state** | Recipe book with no recipes | Shows "Tap + to add a recipe" text | **No import CTA** |

#### Code References -- Entry Points

- **Add Recipe sheet**: `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart` (lines 45-73) -- three options: Photo (`/recipes/add/photo`), Files (`/recipes/add/files`), Manual (`/recipes/add/wizard`)
- **Recipe Book detail menu**: `app/lib/features/recipe_books/recipe_book_detail_screen.dart` (lines 593-641) -- menu items for `import_url`, `import_photo`, `bulk_import`
- **Share sheet handler**: `app/lib/main.dart` (lines 130-180) -- `ReceiveSharingIntent` listens for shared URLs, routes to `/recipes/add/share?url=...`
- **Onboarding**: `app/lib/features/onboarding/onboarding_start_screen.dart` (lines 140-159) -- all three start methods call `completeOnboarding()` and route to home
- **Router**: `app/lib/core/router/app_router.dart` -- all import routes defined at lines 187-250

### Existing Import Flows (Detailed)

#### 1. URL Import (Single)
- **Screen**: `app/lib/features/recipes/add_recipe/url_import_screen.dart`
- **Flow**: User pastes URL -> selects destination book -> clicks "Import" -> API creates ImportJob -> polls for status -> shows recipe preview -> user approves/skips
- **Backend**: `POST /recipe-books/{book_id}/import` with `source_type: "url"` -> `ParseSourceTask` -> `ExtractRecipeTask` (JSON-LD first, AI fallback) -> `MatchIngredientsTask` -> user review -> `ApproveImportItem` -> `CreateRecipeTask`
- **Accessible from**: Recipe book detail menu only (not from Add Recipe sheet)

#### 2. Bulk URL Import
- **Screen**: `app/lib/features/recipes/add_recipe/bulk_url_import_screen.dart`
- **Flow**: User pastes multiple URLs (one per line, max 50) -> validates URLs in real-time -> selects destination book -> batch import with progress tracking -> review/approve all results
- **Backend**: Same pipeline but with `source_type: "url_list"`, creates one ImportItem per URL, fans out extraction tasks in batches of 10
- **Accessible from**: Recipe book detail menu only

#### 3. Photo/OCR Import
- **Screen**: `app/lib/features/recipes/add_recipe/photo_capture_screen.dart`
- **Flow**: User takes photo or picks from gallery (supports multi-select) -> uploads to S3 -> submits parser job(s) -> polls OCR service -> feeds OCR text into import pipeline with `source_type: "photo"` -> preview & approve
- **Parser service**: `services/parser/` -- HunyuanOCR model (tencent/HunyuanOCR), accepts JPEG/PNG/WebP/HEIC, returns markdown text
- **Text extraction**: `libraries/utils/utils/services/recipe_extractors/text_extractor.py` -- uses GPT-4o-mini to structure OCR text into recipe JSON, corrects OCR errors
- **Accessible from**: Add Recipe sheet, Recipe book detail menu

#### 4. Share Sheet Import (iOS)
- **Screen**: `app/lib/features/recipes/add_recipe/share_import_screen.dart`
- **Flow**: User shares a URL from Safari/other app -> Palateful receives it -> auto-starts import to default recipe book -> preview & approve
- **Limitation**: Only handles URLs, not files or text
- **Accessible from**: iOS share sheet (external)

#### 5. File Import (STUB)
- **Screen**: `app/lib/features/recipes/add_recipe/file_import_screen.dart`
- **Status**: Complete stub -- shows "Coming soon! File import uses the same AI as photo OCR." with a "Go Back" button
- **No file picker, no processing, no backend support**

#### 6. Manual Recipe Entry
- **Screen**: `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart`
- **Flow**: 4-step wizard: Name & Photo -> Ingredients -> Instructions -> Details (times, servings, source URL, tags, meal type, book selection)
- **Calls**: `POST /recipes` directly (not the import pipeline)

#### 7. Background Batch Parser
- **Service**: `app/lib/features/recipes/add_recipe/batch_parser_service.dart`
- **Widget**: `app/lib/features/home/widgets/batch_import_status_widget.dart`
- **Purpose**: Allows OCR jobs to run in the background with a status bar on the home screen
- **Note**: This service only handles the OCR phase; it does not pipe results into the import pipeline automatically

### Backend Architecture

#### Import Pipeline (Celery Task Chain)

```
StartImport API -> ParseSourceTask -> ExtractRecipeTask -> MatchIngredientsTask -> [User Review] -> ApproveImportItem -> CreateRecipeTask
```

- **ParseSourceTask** (`libraries/utils/utils/tasks/import_tasks/parse_source_task.py`): Orchestrates initial parsing, fans out to extraction tasks in batches of 10
- **ExtractRecipeTask** (`libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py`): Tiered extraction: JSON-LD -> AI fallback. Also handles raw data (spreadsheet rows) and photo/OCR text
- **MatchIngredientsTask** (`libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py`): Tiered ingredient matching: cached user matches -> exact canonical_name -> pg_trgm fuzzy -> flag for review
- **CreateRecipeTask** (`libraries/utils/utils/tasks/import_tasks/create_recipe_task.py`): Creates Recipe and RecipeIngredient records from approved data

#### Extractor Registry (`libraries/utils/utils/services/recipe_extractors/`)

- **JsonLdExtractor**: Parses Schema.org Recipe JSON-LD from HTML. Handles `@graph`, nested types, HowToSection, ISO 8601 durations. Free.
- **AIExtractor**: GPT-4o-mini fallback. Cleans HTML (removes scripts/styles/nav/header/footer), truncates to 32K chars, costs ~$0.002/recipe.
- **TextExtractor**: GPT-4o-mini for OCR text. Handles OCR error correction, truncates to 16K chars.
- **Extensible**: Registry supports adding extractors with priority. Comments note planned Microdata and site-specific scrapers.

#### Data Model

- **ImportJob** (`libraries/utils/utils/models/import_job.py`): Tracks overall session -- status, source_type (`spreadsheet|pdf|url|url_list`), progress counters, AI cost tracking, links to user and recipe book
- **ImportItem** (`libraries/utils/utils/models/import_item.py`): Individual recipe -- status progression (`pending -> extracting -> matching -> awaiting_review -> approved -> completed`), stores `raw_data`, `parsed_recipe`, `user_edits`, error info, cost tracking

#### Export Endpoint

- **ExportRecipes** (`services/api/src/api/v1/user/export_recipes.py`): Exports all user recipes as JSON with full data (ingredients, steps, notes, versions, tags)
- **Potential**: This export format could serve as an import format for migration between Palateful accounts

### Supported Formats

| Format | Current Support | Backend Ready? |
|---|---|---|
| URL (single) | Working | Yes |
| URL (bulk, up to 50) | Working | Yes |
| Photo (camera/gallery) | Working | Yes |
| Photo (multi-page) | Working (merged OCR text) | Yes |
| CSV/Spreadsheet | **Not implemented** | Partial (source_type exists in model, `_extract_from_raw_data` handles raw dict) |
| PDF | **Not implemented** | Minimal (source_type exists in model, no parser) |
| Text paste | **Not implemented** | Ready (text_extractor exists) |
| JSON (Palateful export) | **Not implemented** | Not yet |
| JSON-LD (schema.org) | Via URL only | Extractor exists |
| Meal Master / other formats | **Not implemented** | No |
| Other app exports (Paprika, Mela) | **Not implemented** | No |

---

## User Journey Import Touchpoints

### Where Import SHOULD Be Available (Gap Analysis)

#### 1. First-Time Onboarding
- **Current**: "Import From Existing Source" card exists but does nothing except complete onboarding
- **Desired**: Should route to a dedicated import hub showing all available methods (URL, photo, file upload, text paste). Or better: after onboarding completes, show an import prompt/modal
- **Priority**: HIGH -- first impression, biggest drop-off risk

#### 2. Empty State in Recipe Book
- **Current**: Shows text "Tap + to add a recipe to this book" with no action
- **Desired**: Rich empty state with import CTAs: "Import from URL", "Upload a file", "Take a photo", "Paste a recipe"
- **Priority**: HIGH -- this is the moment the user most wants to fill their book

#### 3. The "+" / Add Recipe Button
- **Current**: Bottom sheet with Photo, Files (stub), Manual. No URL import option.
- **Desired**: Should include all available import methods: URL, Photo, File/Spreadsheet, Paste Text, Manual. Consider a redesigned sheet that groups: "Quick Add" (URL, Photo) vs "Build from Scratch" (Manual, AI Chat)
- **Priority**: HIGH -- primary import entry point

#### 4. From Receiving a Shared Link/File (Share Sheet)
- **Current**: Works for URLs via `ReceiveSharingIntent`. Does not handle shared files.
- **Desired**: Handle shared files (CSV, PDF, images), shared text (copied recipe), and URLs. An iOS Share Extension would provide a native feel.
- **Priority**: MEDIUM -- works for URLs already, file support would be a big upgrade

#### 5. Bulk Migration from Another App
- **Current**: Bulk URL import (up to 50 URLs). No file-based bulk import.
- **Desired**: Import from Paprika (.paprikarecipes), Mela (.melarecipes), CopyMeThat (CSV export), Crouton (JSON), general CSV/spreadsheet, Palateful's own export format. A dedicated "Migration" screen with app-specific guides.
- **Priority**: MEDIUM-HIGH -- critical for user acquisition from competitor apps

#### 6. Photo of a Recipe Card/Page
- **Current**: Working via photo capture screen. Multi-image supported.
- **Desired**: Improve with auto-cropping, batch processing for entire cookbook (scan multiple pages, detect recipe boundaries), and "quick scan" from the home screen
- **Priority**: MEDIUM -- already functional, can iterate

#### 7. Paste Text
- **Current**: Not available anywhere
- **Desired**: A "Paste Recipe" option that accepts free-form text (copied from email, message, web page) and uses AI to structure it
- **Priority**: HIGH -- extremely common use case, especially on mobile where copying a recipe from a message or email is natural

#### 8. AI Chat Integration
- **Current**: Chat feature exists but not connected to import
- **Desired**: "Add this to my recipe book" button on AI-generated recipes in chat
- **Priority**: LOW-MEDIUM -- nice to have

---

## Research Findings: Competitor Import Flows

### Paprika Recipe Manager
- **Import methods**: URL (auto-detect recipe), clipboard paste, manual entry, browser extension
- **Bulk**: Import from Paprika 2, import from other apps (specific format support)
- **Export**: `.paprikarecipes` format (ZIP of gzipped JSON files)
- **Key insight**: Browser extension and clipboard import are most-used features. Their URL import is extremely reliable with site-specific scrapers.

### Mela (iOS)
- **Import methods**: URL (share sheet is primary), Safari extension, manual entry
- **Bulk**: Import from Paprika, Mela 1, `.melarecipes` backup
- **Key insight**: Share sheet is the primary import method. One-tap from Safari. Minimal friction.
- **UX pattern**: After import from share sheet, shows a "Recipe saved" notification -- does not require review. Trust the AI.

### Pestle
- **Import methods**: URL (share sheet), photo/OCR, manual entry
- **Bulk**: Not supported
- **Key insight**: OCR import is a standout feature. They process photos of recipe cards and cookbooks with high accuracy.

### Crouton
- **Import methods**: URL, share sheet, manual, clipboard paste
- **Bulk**: CSV import, Crouton backup
- **Key insight**: CSV import with column mapping is well-executed. Users map their spreadsheet columns to recipe fields.

### CopyMeThat
- **Import methods**: Browser extension (primary), URL, manual
- **Bulk**: CSV import, import from other CopyMeThat accounts
- **Export**: CSV, PDF
- **Key insight**: Browser extension approach makes web-based recipe collection seamless

### Common Patterns Across Competitors

1. **Share sheet is king**: The most used import method across all apps. One tap from any browser or app.
2. **Auto-approve for high-confidence imports**: Mela and Paprika don't require review for JSON-LD extractions. They just save and show a notification.
3. **Browser extensions matter on desktop**: Not applicable for mobile-first, but relevant if Palateful adds a web app
4. **CSV/spreadsheet import with column mapping**: Crouton and CopyMeThat both support this for bulk migration
5. **App-specific import wizards**: Most apps support importing from at least 2-3 competitor formats

### Spreadsheet/CSV Import Patterns

The typical CSV import flow is:

1. **Upload file** (file picker or drag-and-drop)
2. **Preview & map columns**: Show first few rows, let user map columns to recipe fields (name, ingredients, instructions, servings, etc.)
3. **Handle multi-row ingredients**: Some spreadsheets have one ingredient per row with recipe name repeated, others have all ingredients in one cell separated by newlines
4. **Batch process**: Create import items for each recipe row
5. **Review**: Show all extracted recipes with status
6. **Approve/edit individually or in bulk**

### Recipe Exchange Formats

| Format | Description | Adoption |
|---|---|---|
| **Schema.org Recipe (JSON-LD)** | Web standard, embedded in HTML | Ubiquitous on recipe websites |
| **Recipe JSON-LD (standalone)** | Same schema, standalone file | Rare as a file format |
| **Meal Master** | Legacy plain text format | Old but huge archive (rec.food.recipes) |
| **RecipeML** | XML-based recipe format | Mostly dead |
| **CookML** | German recipe XML format | Regional |
| **Paprika (.paprikarecipes)** | ZIP of gzipped JSON | Paprika users only |
| **Mela (.melarecipes)** | Proprietary backup format | Mela users only |
| **Crouton (JSON)** | JSON export | Crouton users only |
| **CSV/TSV** | Tabular data | Universal but no standard schema |
| **Plain text** | Unstructured recipe text | Universal -- requires AI parsing |

---

## Proposed Import Architecture

### Unified Import Hub

Replace the current fragmented entry points with a unified import hub accessible from all touchpoints:

```
                         Import Hub
                    /    |    |    |    \
                  URL  Photo  File  Paste  Scan
                   |     |     |     |      |
              +---------+---------+---------+
              |   Unified Import Pipeline   |
              +---------+---------+---------+
                        |
              +---------+---------+
              |   Review Screen   |
              |  (if needed)      |
              +---------+---------+
                        |
                  Recipe Created
```

### Import Methods (Prioritized)

#### Tier 1 -- Must Have (address core pain points)
1. **URL Import** -- already working, needs to be more discoverable (add to Add Recipe sheet)
2. **Text Paste Import** -- new; paste recipe text from any source, AI structures it
3. **CSV/Spreadsheet Import** -- new; file picker, column mapping, batch processing
4. **Enhanced Onboarding Import** -- route "Import From Existing Source" to actual import hub

#### Tier 2 -- Should Have
5. **File Import (general)** -- PDF, image files from Files app
6. **Shared File Handling** -- accept files via share sheet, not just URLs
7. **Auto-approve for high-confidence extractions** -- skip review step when JSON-LD extraction succeeds cleanly

#### Tier 3 -- Nice to Have
8. **App-specific importers** -- Paprika, Mela, CopyMeThat formats
9. **Palateful export re-import** -- import from Palateful's own JSON export
10. **iOS Share Extension** -- native share extension for faster imports
11. **Bulk photo scan** -- scan entire cookbook with page-turn detection

### Backend Changes Required

#### New: Spreadsheet Parser
- Accept CSV, XLSX via file upload to S3
- Parse using `pandas` or `openpyxl`
- Column auto-detection (heuristics + AI) with manual mapping fallback
- Create ImportItem per recipe row
- Feed into existing extraction pipeline

#### New: Text Import Source Type
- Accept raw text via API
- Route to `TextExtractor` (already exists, used for OCR text)
- Same pipeline: extract -> match ingredients -> review -> create

#### Enhancement: File Upload Endpoint
- Accept file uploads (CSV, XLSX, PDF, images) via `POST /recipe-books/{book_id}/import/file`
- Upload to S3, create ImportJob with appropriate source_type
- Route to correct parser based on file extension/MIME type

#### Enhancement: Auto-Approve Logic
- If extraction used JSON-LD (structured data) AND all ingredients matched with high confidence (>0.85), auto-approve without user review
- Config flag to enable/disable per user preference
- Reduces friction for the common case (importing from well-structured recipe sites)

---

## Recommendations (Prioritized)

### P0 -- Critical (address the stated pain points)

1. **Add URL Import to the Add Recipe sheet**
   - Currently missing from the primary entry point
   - Simple UI change: add a 4th option "URL" between Photo and Manual
   - Effort: XS (< 1 hour)

2. **Implement Text Paste Import**
   - New screen: large text input area, "Extract Recipe" button
   - Backend already supports this via `text_extractor.py`
   - Needs: new Flutter screen, new `source_type: "text"` in StartImport
   - Effort: S (1-2 days)

3. **Fix Onboarding Import Flow**
   - "Import From Existing Source" should route to the import hub after onboarding completes
   - Currently just calls `completeOnboarding()` and goes home
   - Should: complete onboarding, then navigate to `/recipes/add` or show a modal with import options
   - Effort: S (< 1 day)

4. **Implement CSV/Spreadsheet Import**
   - This is THE pain point: "mom shared her spreadsheet"
   - File picker for CSV/XLSX
   - Column mapping screen (show first 3 rows, let user map to recipe fields)
   - Backend: new task to parse spreadsheet, create ImportItems
   - Effort: M-L (3-5 days)

### P1 -- Important

5. **Add Import CTA to empty recipe book state**
   - When a book has no recipes, show rich empty state with import options
   - "Import recipes from URL, photo, or file"
   - Effort: XS (< 1 day)

6. **Add Bulk Text Paste**
   - Accept multiple recipes in one text block (separated by "---" or detected by AI)
   - Reuse existing bulk import review flow
   - Effort: S (1-2 days)

7. **Accept shared files via share sheet**
   - Extend `ReceiveSharingIntent` handler to accept file types (CSV, PDF, images)
   - Route to appropriate import screen
   - Effort: S-M (2-3 days)

8. **Auto-approve high-confidence imports**
   - Skip review for JSON-LD extractions where all ingredients match
   - Show "Recipe saved" notification instead of review screen
   - User preference toggle in settings
   - Effort: S (1-2 days)

### P2 -- Nice to Have

9. **App-specific importers** (Paprika, Mela, Crouton)
   - Each app has a specific export format
   - Parse format, create ImportItems, use existing review flow
   - Effort: M per format (2-3 days each)

10. **PDF import**
    - Use OCR pipeline for scanned PDFs
    - Use text extraction for text-based PDFs
    - Detect recipe boundaries in multi-recipe PDFs
    - Effort: M (3-5 days)

11. **iOS Share Extension**
    - Native share extension for faster import experience
    - Handles URL extraction and recipe save without opening full app
    - Effort: L (5-7 days, requires native iOS development)

12. **Redesigned Import Hub**
    - Dedicated import screen grouping all methods
    - "Quick Import" (URL, photo) vs "Bulk Import" (spreadsheet, multi-URL) vs "Manual"
    - In-progress imports visible (like batch status widget but for all imports)
    - Effort: M (3-4 days)

---

## Technical Considerations

### Spreadsheet Import Architecture

The spreadsheet import is the highest-effort new feature. Key decisions:

**Column Mapping Strategy**:
- **Option A**: AI auto-detect columns (send first 5 rows to GPT-4o-mini, ask it to map columns). Cost: ~$0.001 per spreadsheet. Pros: zero-friction. Cons: AI cost, possible errors.
- **Option B**: Heuristic auto-detect + manual override (check header row for keywords like "name", "ingredients", "instructions"). Pros: free, fast. Cons: misses unconventional headers.
- **Recommendation**: Option B with Option A as fallback. Try heuristics first, if confidence is low, use AI. Always show column mapping UI for user verification.

**Ingredient Format in Spreadsheets**:
- Some spreadsheets have one cell with all ingredients (newline-separated)
- Some have one ingredient per row with recipe name repeated
- Some have separate columns for each ingredient
- Need AI or heuristics to detect which format is used

**File Size Limits**:
- Cap at 5MB for CSV, 10MB for XLSX
- Max 200 recipes per import (expand from current 50-URL limit)
- Process in batches of 10 (matching current URL batch size)

### Text Paste Import

- Reuse `extract_recipe_from_text()` from `text_extractor.py`
- For multi-recipe text, add a new AI prompt that splits text into individual recipes first
- Max text length: 16K chars (matching existing limit)
- Cost: ~$0.001-0.002 per paste

### Performance Considerations

- Bulk imports (50+ items) already fan out Celery tasks in batches of 10
- Spreadsheet imports could have 200+ items -- may need larger batches or rate limiting
- OCR pipeline is the slowest path (~30-60 seconds per image)
- JSON-LD extraction is essentially free and instant
- AI extraction costs ~$0.002 per recipe -- at scale, spreadsheet imports of 200 recipes = ~$0.40

### Mobile UX Considerations

- **Paste is the weakest link on mobile**: Consider a "Paste from clipboard" button that auto-detects clipboard content (URL vs text vs nothing)
- **File picker on iOS**: Use `file_picker` package for CSV/XLSX; `image_picker` already handles photos
- **Long-running imports**: Already handled well -- polling with background processing, progress indicators
- **Offline resilience**: Import items are persisted in DB; if app closes, user can resume from import review screen

---

## Estimated Complexity

| Item | Frontend | Backend | Total |
|---|---|---|---|
| Add URL to Add Recipe sheet | XS (1h) | None | **XS** |
| Fix onboarding import routing | XS (2h) | None | **XS** |
| Empty state import CTA | XS (2h) | None | **XS** |
| Text paste import screen | S (1d) | XS (4h) | **S** |
| CSV/Spreadsheet import | M (3d) | M (3d) | **L** |
| Accept shared files | S (1d) | XS (2h) | **S** |
| Auto-approve high-confidence | XS (2h) | S (4h) | **S** |
| Bulk text paste | S (1d) | S (1d) | **M** |
| Paprika format importer | S (1d) | M (2d) | **M** |
| PDF import | M (2d) | M (3d) | **L** |
| iOS Share Extension | L (5d) | None | **L** |
| Import Hub redesign | M (3d) | None | **M** |

**Suggested sprint plan**:
- **Sprint 1 (quick wins)**: URL in Add sheet, fix onboarding, empty state CTA, text paste import -- **3-4 days**
- **Sprint 2 (core gap)**: CSV/spreadsheet import end-to-end -- **5-6 days**
- **Sprint 3 (polish)**: Auto-approve, shared files, bulk text paste -- **3-4 days**
- **Sprint 4 (expansion)**: Paprika importer, PDF import, Import Hub redesign -- **7-8 days**

---

## Appendix: Key File Paths

### Flutter App (Import Screens)
- `app/lib/features/recipes/add_recipe/add_recipe_sheet.dart` -- Add Recipe bottom sheet
- `app/lib/features/recipes/add_recipe/url_import_screen.dart` -- Single URL import
- `app/lib/features/recipes/add_recipe/bulk_url_import_screen.dart` -- Bulk URL import
- `app/lib/features/recipes/add_recipe/photo_capture_screen.dart` -- Photo/OCR import
- `app/lib/features/recipes/add_recipe/file_import_screen.dart` -- File import (STUB)
- `app/lib/features/recipes/add_recipe/share_import_screen.dart` -- Share sheet import
- `app/lib/features/recipes/add_recipe/import_review_list_screen.dart` -- Bulk review list
- `app/lib/features/recipes/add_recipe/import_item_review_screen.dart` -- Individual item review/edit
- `app/lib/features/recipes/add_recipe/recipe_wizard_screen.dart` -- Manual entry wizard
- `app/lib/features/recipes/add_recipe/batch_parser_service.dart` -- Background OCR service
- `app/lib/features/home/widgets/batch_import_status_widget.dart` -- Background job status bar
- `app/lib/features/onboarding/onboarding_start_screen.dart` -- Onboarding start method selection
- `app/lib/core/router/app_router.dart` -- Route definitions

### Backend (Import Pipeline)
- `services/api/src/api/v1/import_job/start_import.py` -- StartImport endpoint
- `services/api/src/api/v1/import_job/approve_import_item.py` -- Approve endpoint
- `services/api/src/routers/v1/import_router.py` -- Import API routes

### Backend (Tasks)
- `libraries/utils/utils/tasks/import_tasks/parse_source_task.py` -- Source parsing orchestrator
- `libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py` -- Recipe extraction (tiered)
- `libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py` -- Ingredient matching
- `libraries/utils/utils/tasks/import_tasks/create_recipe_task.py` -- Recipe creation

### Backend (Extractors)
- `libraries/utils/utils/services/recipe_extractors/__init__.py` -- Extractor registry
- `libraries/utils/utils/services/recipe_extractors/base.py` -- Base classes (ExtractedRecipe, ExtractionResult)
- `libraries/utils/utils/services/recipe_extractors/json_ld.py` -- JSON-LD extractor
- `libraries/utils/utils/services/recipe_extractors/ai_extractor.py` -- GPT-4o-mini HTML extractor
- `libraries/utils/utils/services/recipe_extractors/text_extractor.py` -- GPT-4o-mini text/OCR extractor

### Backend (Models)
- `libraries/utils/utils/models/import_job.py` -- ImportJob model
- `libraries/utils/utils/models/import_item.py` -- ImportItem model

### Backend (Parser Service)
- `services/parser/src/main.py` -- OCR FastAPI service
- `services/parser/src/model.py` -- HunyuanOCR model loading/inference
- `services/parser/src/config.py` -- Parser config

### Backend (Export)
- `services/api/src/api/v1/user/export_recipes.py` -- JSON export endpoint
