# Story MCP.4: Import & OCR Tools (3 tools)

Status: ready-for-dev

## Story

As a user talking to Claude,
I want to say "import this recipe from [URL/text/photo]" and have it handled,
so that I can add recipes from any source through conversation.

## Acceptance Criteria

1. `import_recipe(source_type, url?, text?, image_base64?, additional_context?, book_id?)` — returns `{job_id, status, message}` immediately, never blocks
2. `source_type="url"` → delegates to StartImport with URL
3. `source_type="text"` → StartImport with raw text, appends optional `additional_context`
4. `source_type="photo"` → StartImport photo path (requires `ocr_texts` already available in the existing endpoint; for this story we rely on Claude's pre-OCR by passing extracted text via `text`)
5. `get_import_status(job_id)` → GetImportJob + ListImportItems combined
6. `approve_import(item_id)` → ApproveImportItem
7. Tool descriptions explain the async pattern
8. Error cases: unknown source_type, empty url/text, missing default book

## Technical Approach

- `import_recipe` maps to `StartImport.Params` based on source_type
- For text imports, concatenate `additional_context` into `raw_text`
- For photo, require `ocr_texts` parameter (Claude extracts text first); full server-side OCR via image_base64 is reserved for a future story since it requires S3 presigned upload wiring and parser batch — out of scope for the zero-hands import loop
- `get_import_status` calls GetImportJob first, then ListImportItems, merges into one JSON response
- All tools use `call_endpoint()` with book_id defaulting to user's `default_recipe_book_id` when not provided

## File List

- Create: `services/api/src/mcp_server/tools/import_tools.py`
- Modify: `services/api/src/mcp_server/tools/__init__.py`
- Create: `services/api/tests/mcp_server/test_import_tools.py`
