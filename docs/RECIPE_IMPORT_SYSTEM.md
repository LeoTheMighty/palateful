# Recipe Import System - Design Document

## Overview

A comprehensive, worker-based import system that handles multiple source types (spreadsheets with URLs, PDFs, web links) with asynchronous processing, cost-effective AI usage, and user notification for review/assistance.

---

## User Preferences (From Discussion)

- **Spreadsheet format**: Mix of full recipe data and URL-only rows
- **New ingredients**: Auto-create with `pending_review=True`
- **Images**: Download thumbnails to S3 for reliability
- **Review flow**: Auto-approve high-confidence, review only flagged items
- **Scraping strategy**: Site-specific scrapers + structured data + AI fallback
- **App flow**: Background processing with push notifications
- **Agent integration**: Hybrid - pipeline for bulk, notifications for user review

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Import Pipeline                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│   Flutter App                    API                         Worker               │
│   ┌──────────┐              ┌──────────┐              ┌──────────────────┐      │
│   │ Upload   │─────────────▶│ Start    │─────────────▶│ ParseSourceTask  │      │
│   │ File/URL │              │ Import   │              │ (fan out items)  │      │
│   └──────────┘              └──────────┘              └────────┬─────────┘      │
│        │                                                       │                 │
│        │                                                       ▼                 │
│        │                                              ┌──────────────────┐      │
│        │                                              │ ExtractRecipeTask│      │
│        │                                              │ (per item batch) │      │
│        │                                              └────────┬─────────┘      │
│        │                                                       │                 │
│        │                                                       ▼                 │
│        │                                              ┌──────────────────┐      │
│        │                                              │MatchIngredients  │      │
│        │                                              │ Task (tiered)    │      │
│        │                                              └────────┬─────────┘      │
│        │                                                       │                 │
│        │         ┌─────────────────────────────────────────────┼─────────┐      │
│        │         │                                             │         │      │
│        │         ▼                                             ▼         │      │
│        │   High Confidence                              Low Confidence   │      │
│        │   ┌──────────────┐                            ┌─────────────┐   │      │
│        │   │ Auto-approve │                            │ Flag for    │   │      │
│        │   │ + Create     │                            │ Review      │   │      │
│        │   └──────────────┘                            └──────┬──────┘   │      │
│        │                                                      │          │      │
│        │◀─────────── Push Notification ───────────────────────┘          │      │
│        │         "3 recipes need your review"                            │      │
│        │                                                                 │      │
│        ▼                                                                 │      │
│   ┌──────────┐                                                           │      │
│   │ Review   │──── User approves/edits ─────────────────────────────────▶│      │
│   │ Screen   │                                              ┌────────────┘      │
│   └──────────┘                                              ▼                   │
│                                                    ┌──────────────────┐         │
│                                                    │ CreateRecipeTask │         │
│                                                    │ (finalize)       │         │
│                                                    └──────────────────┘         │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Models

### 1. ImportJob

Tracks the overall import session.

```python
# /libraries/utils/utils/models/import_job.py

class ImportJob(Base):
    __tablename__ = "import_jobs"

    # Status: pending | processing | awaiting_review | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Source info
    source_type: Mapped[str]  # spreadsheet | pdf | url | url_list
    source_filename: Mapped[str | None]
    source_s3_key: Mapped[str | None]  # For uploaded files

    # Progress
    total_items: Mapped[int] = mapped_column(default=0)
    processed_items: Mapped[int] = mapped_column(default=0)
    succeeded_items: Mapped[int] = mapped_column(default=0)
    failed_items: Mapped[int] = mapped_column(default=0)
    pending_review_items: Mapped[int] = mapped_column(default=0)

    # Cost tracking (in cents)
    total_ai_cost_cents: Mapped[int] = mapped_column(default=0)

    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    recipe_book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipe_books.id"))

    # Timestamps
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
```

### 2. ImportItem

Individual recipe within an import job.

```python
# /libraries/utils/utils/models/import_item.py

class ImportItem(Base):
    __tablename__ = "import_items"

    # Status: pending | extracting | matching | awaiting_review | approved | completed | failed | skipped
    status: Mapped[str] = mapped_column(String(20), default="pending")

    # Source reference
    source_type: Mapped[str]  # row | url | pdf_page
    source_reference: Mapped[str | None]  # Row number, page number
    source_url: Mapped[str | None]

    # Data stages
    raw_data: Mapped[dict] = mapped_column(JSONB, default={})
    parsed_recipe: Mapped[dict | None] = mapped_column(JSONB)  # Extracted recipe
    user_edits: Mapped[dict | None] = mapped_column(JSONB)     # User modifications

    # Error handling
    error_message: Mapped[str | None]
    error_code: Mapped[str | None]
    retry_count: Mapped[int] = mapped_column(default=0)

    # Cost tracking
    ai_cost_cents: Mapped[int] = mapped_column(default=0)

    # Foreign keys
    import_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_jobs.id"))
    created_recipe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recipes.id"))
```

### 3. IngredientMatch (Learning Cache)

Caches ingredient matching decisions to reduce AI calls over time.

```python
# /libraries/utils/utils/models/ingredient_match.py

class IngredientMatch(Base):
    __tablename__ = "ingredient_matches"

    source_text: Mapped[str]  # Original text like "2 cups flour"
    matched_ingredient_id: Mapped[uuid.UUID | None]
    match_type: Mapped[str]  # exact | fuzzy | ai | user_selected
    confidence: Mapped[float]
    user_confirmed: Mapped[bool | None]  # User validated this match
    user_id: Mapped[uuid.UUID | None]
```

---

## Task Pipeline

### Task 1: ParseSourceTask

Parses the source file/URLs and creates ImportItem records.

```python
# /libraries/utils/utils/tasks/import_tasks/parse_source_task.py

class ParseSourceTask(BaseTask):
    name = "parse_source_task"

    def execute(self, import_job_id: str):
        # 1. Load import job
        # 2. Based on source_type:
        #    - spreadsheet: Parse CSV/Excel, create item per row
        #    - url_list: Create item per URL
        #    - pdf: Detect recipe boundaries, create items
        # 3. Update job.total_items
        # 4. Fan out to ExtractRecipeTask in batches
```

**Spreadsheet Parsing Logic:**
- Detect columns intelligently (name, url, ingredients, instructions, etc.)
- If row has URL → mark for URL extraction
- If row has full data → mark for direct parsing

### Task 2: ExtractRecipeTask

Extracts structured recipe data using tiered approach.

```python
# /libraries/utils/utils/tasks/import_tasks/extract_recipe_task.py

class ExtractRecipeTask(BaseTask):
    name = "extract_recipe_task"

    def execute(self, item_ids: list[str]):
        for item in items:
            if item.source_url:
                parsed = self._extract_from_url(item)
            else:
                parsed = self._extract_from_row(item)

            # Update item with parsed data
            # Trigger MatchIngredientsTask
```

**URL Extraction Tiers (Cost Optimization):**

| Tier | Method | Cost | Success Rate |
|------|--------|------|--------------|
| 1 | JSON-LD (Schema.org) | Free | ~60% of recipe sites |
| 2 | Site-specific scraper | Free | Popular sites |
| 3 | Microdata/RDFa | Free | Older sites |
| 4 | AI extraction (gpt-4o-mini) | ~$0.002 | Fallback |

**Site-Specific Scrapers to Build:**
- AllRecipes
- Food Network
- Epicurious
- Serious Eats
- NYT Cooking
- Budget Bytes
- Bon Appetit

### Task 3: MatchIngredientsTask

Matches ingredient text to existing ingredients.

```python
# /libraries/utils/utils/tasks/import_tasks/match_ingredients_task.py

class MatchIngredientsTask(BaseTask):
    name = "match_ingredients_task"

    def execute(self, item_id: str):
        for ingredient in parsed_recipe.ingredients:
            match = self._match_ingredient(ingredient.text)
            ingredient.ingredient_id = match.id
            ingredient.confidence = match.confidence
            ingredient.needs_review = match.confidence < 0.85
```

**Ingredient Matching Tiers:**

| Tier | Method | Cost | When Used |
|------|--------|------|-----------|
| 1 | Previous user-confirmed match | Free | Same text seen before |
| 2 | Exact canonical_name/alias | Free | Direct match |
| 3 | pg_trgm fuzzy (>0.85) | Free | High similarity |
| 4 | pg_trgm fuzzy (>0.5) | Free | Needs review |
| 5 | Semantic search (embeddings) | Free* | No fuzzy match |
| 6 | AI disambiguation | ~$0.001 | Ambiguous cases |

*Free if embeddings pre-computed

**Auto-Create New Ingredients:**
- If no match found, create ingredient with `pending_review=True`
- Store in IngredientMatch for future reference

### Task 4: ProcessImageTask

Downloads and creates thumbnails for recipe images.

```python
# /libraries/utils/utils/tasks/import_tasks/process_image_task.py

class ProcessImageTask(BaseTask):
    name = "process_image_task"

    def execute(self, item_id: str, image_url: str):
        # 1. Download image
        # 2. Validate (is it actually an image?)
        # 3. Create thumbnail (e.g., 400x300)
        # 4. Upload to S3: imports/{job_id}/{item_id}/thumb.jpg
        # 5. Update item.parsed_recipe.image_url with S3 URL
```

**Image Handling:**
- Download to temp file
- Validate MIME type
- Resize to thumbnail (preserve aspect ratio, max 400px)
- Upload to S3 with public-read ACL
- Store S3 URL in recipe

### Task 5: CreateRecipeTask

Creates the actual Recipe record from approved items.

```python
# /libraries/utils/utils/tasks/import_tasks/create_recipe_task.py

class CreateRecipeTask(BaseTask):
    name = "create_recipe_task"

    def execute(self, item_id: str):
        # 1. Get item (must be status=approved)
        # 2. Use user_edits if present, else parsed_recipe
        # 3. Create Recipe record
        # 4. Create RecipeIngredient records
        # 5. Update item.created_recipe_id
        # 6. Update job counts
```

### Task 6: NotifyImportStatusTask

Sends push notifications at key points.

```python
# Notification triggers:
# - Job started: "Importing X recipes..."
# - Needs review: "3 recipes need your attention"
# - Completed: "Successfully imported X recipes"
# - Failed: "Import failed - please try again"
```

---

## API Endpoints

### Import Job Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/recipe-books/{book_id}/import` | Start new import |
| GET | `/v1/import-jobs/{job_id}` | Get job status/progress |
| GET | `/v1/import-jobs/{job_id}/items` | List items (filterable) |
| DELETE | `/v1/import-jobs/{job_id}` | Cancel import |

### Import Item Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/import-items/{item_id}` | Get item details |
| PUT | `/v1/import-items/{item_id}` | Update/edit item |
| POST | `/v1/import-items/{item_id}/approve` | Approve item |
| POST | `/v1/import-items/{item_id}/skip` | Skip item |
| POST | `/v1/import-jobs/{job_id}/approve-all` | Bulk approve |

### File Upload

```python
# POST /v1/recipe-books/{book_id}/import
# Content-Type: multipart/form-data

{
    "source_type": "spreadsheet",  # or "pdf", "url", "url_list"
    "file": <binary>,              # For spreadsheet/pdf
    "urls": ["url1", "url2"],      # For url/url_list
}

# Response:
{
    "import_job_id": "uuid",
    "status": "pending",
    "total_items": 0  # Updated after parsing
}
```

---

## Cost Optimization Summary

**Target: < $0.01 per recipe imported**

| Operation | Estimated Cost | Optimization |
|-----------|---------------|--------------|
| URL fetch | Free | Cached/rate-limited |
| JSON-LD parse | Free | First attempt always |
| Site scraper | Free | Popular sites covered |
| AI extraction | ~$0.002 | Last resort only |
| Ingredient exact match | Free | Cached lookups |
| Ingredient fuzzy match | Free | pg_trgm in Postgres |
| Ingredient AI match | ~$0.001 | Only for ambiguous |
| Image download | Free | Just bandwidth |
| Image thumbnail | Free | Local processing |
| S3 storage | ~$0.0001 | Thumbnails only |

**Cost Tracking:**
- Track AI costs per item and per job
- Show user estimated cost before starting
- Alert if job exceeds threshold

---

## File Structure

```
libraries/utils/utils/
├── models/
│   ├── import_job.py
│   ├── import_item.py
│   └── ingredient_match.py
├── tasks/
│   └── import_tasks/
│       ├── __init__.py
│       ├── parse_source_task.py
│       ├── extract_recipe_task.py
│       ├── match_ingredients_task.py
│       ├── process_image_task.py
│       ├── create_recipe_task.py
│       └── notify_task.py

services/api/src/
├── api/v1/import_job/
│   ├── start_import.py
│   ├── get_import_job.py
│   ├── list_import_items.py
│   ├── update_import_item.py
│   ├── approve_import_item.py
│   └── cancel_import_job.py
├── schemas/import_job.py
└── routers/v1/import_router.py

libraries/utils/utils/services/
└── recipe_extractors/
    ├── __init__.py
    ├── base.py              # BaseExtractor
    ├── json_ld.py           # JSON-LD parser
    ├── allrecipes.py        # Site-specific
    ├── food_network.py
    ├── epicurious.py
    └── ai_extractor.py      # AI fallback
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (MVP)
1. Create ImportJob, ImportItem models
2. Create database migration
3. Implement ParseSourceTask for URL imports
4. Implement ExtractRecipeTask with JSON-LD only
5. Basic API endpoints (start, status, list)
6. Basic notification on completion

### Phase 2: Ingredient Matching
1. Create IngredientMatch model
2. Implement tiered matching logic
3. Auto-create ingredients with pending_review
4. Review API endpoints

### Phase 3: Site-Specific Extractors
1. Implement BaseExtractor pattern
2. Add AllRecipes, Food Network extractors
3. Add AI fallback extractor
4. Add more sites as needed

### Phase 4: Spreadsheet Support
1. CSV parser with column detection
2. Excel parser
3. Handle mixed URL/data rows

### Phase 5: Image Handling
1. ProcessImageTask
2. S3 upload integration
3. Thumbnail generation

### Phase 6: Polish
1. Push notifications
2. Cost tracking UI
3. Batch operations
4. Error recovery/retry

---

## Verification Plan

1. **Unit Tests:**
   - Test each extractor (JSON-LD, site-specific, AI)
   - Test ingredient matching tiers
   - Test task execution

2. **Integration Tests:**
   - End-to-end URL import
   - Spreadsheet import
   - Review flow

3. **Manual Testing:**
   - Import from user's actual spreadsheet
   - Test popular recipe sites
   - Test notification flow on device

---

## Open Questions Resolved

| Question | Decision |
|----------|----------|
| Use agent library? | Hybrid - pipeline for bulk, agent tools for troubleshooting later |
| Web search as tool? | Not needed - direct URL fetch instead |
| Image copyright? | Download thumbnails only, store in our S3 |
| Write to SQL as tool? | CreateRecipeTask handles this directly |
| Block agent execution? | No - async pipeline with notification-based review |

---

*Last updated: January 2025*
