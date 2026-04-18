# sbf-5 QA Walkthrough — social URL routing at endpoint

**Story:** sbf-5-social-url-routing-promoted-to-endpoint
**Status:** done

## What shipped

- `POST /v1/recipe-books/{id}/import` with a social URL now persists
  `ImportItem.source_type="video"` at creation time, not later inside
  the extractor. `raw_data.detected_platform` carries which platform
  (`tiktok` / `instagram` / `youtube` / `pinterest` / `facebook`) so
  Activity Hub rows can label correctly from the first render.
- Web URLs stay `source_type="url"` with no platform marker.
- `extract_recipe_task`'s existing social check is unchanged —
  remains as a defensive fallback for URLs the classifier might miss
  as the pattern list evolves.

## Manual smoke test

### 1. TikTok import

```bash
curl -X POST $API/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -d '{"source_type":"url","url":"https://www.tiktok.com/@somechef/video/7123456789012345678"}'
```

Expected:
- 201 response with `source_type: "url"` on the JOB (the job retains
  its outer `source_type` per caller intent; only the ITEM gets
  promoted).
- `ImportItem.source_type = "video"` in the DB.
- `ImportItem.raw_data = {"detected_platform": "tiktok"}`.
- Activity Hub row labels "Importing from TikTok video" (copy
  already lives in the source_label logic — unchanged).

### 2. Instagram Reel

```bash
curl -X POST $API/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -d '{"source_type":"url","url":"https://www.instagram.com/reel/CxYzAbc/"}'
```

Expected: same shape as TikTok case, `detected_platform="instagram"`.

### 3. Regular web page

```bash
curl -X POST $API/v1/recipe-books/$BOOK_ID/import \
  -H "Authorization: Bearer $JWT" \
  -d '{"source_type":"url","url":"https://bonappetit.com/recipe/pasta"}'
```

Expected:
- 201 as usual.
- `ImportItem.source_type = "url"` (unchanged).
- `ImportItem.raw_data = {}` — no `detected_platform` key.

### 4. Extract-task fallback still works

Drop a URL that the endpoint DOESN'T classify (e.g. a new TikTok
sub-domain we haven't added to `_PLATFORM_PATTERNS`) into
`extract_recipe_task` directly. The defensive fallback in
`_extract_single_item` should still route it to the video extractor.
Not an end-to-end assertion here — just confirming the old code path
didn't get pulled out.

## What's NOT in this story (don't QA here)

- Activity Hub visual treatment for platform-specific labels —
  downstream of Activity Hub Redesign / epic-import-row-rich-detail.
- url_list promotion — not in scope per AC.
- Deeper platform-specific extraction logic — unchanged.

## Automated test coverage

```
services/api/tests/test_url_classifier.py::TestDetectPlatform              # 21 tests
services/api/tests/test_import.py::TestStartImportSocialUrlRouting         # 3 tests
```

All pass under `DATABASE_URL=postgresql://test/test poetry run pytest`.
