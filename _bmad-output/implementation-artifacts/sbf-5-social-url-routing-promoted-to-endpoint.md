# Story sbf-5: social URL routing promoted to endpoint

**Status:** done
**Epic:** epic-share-backend-foundations

## Goal

Decide `ImportItem.source_type` at creation time when the caller sent
a TikTok / Instagram / YouTube / Pinterest / Facebook URL, so the
Activity Hub and the downstream extractor both see the "this is a
social video" signal *before* any work runs. Today the same decision
lives only inside `extract_recipe_task._extract_single_item`, which
means the ImportItem is persisted as `source_type="url"` and the UI
has no way to label the row as a TikTok / Instagram / etc. import
until after extraction finishes (if at all).

## Scope

- `POST /v1/recipe-books/{id}/import` with `source_type="url"` and a
  social URL → `ImportItem.source_type = "video"` at creation.
- `ImportItem.raw_data.detected_platform` gets the platform string
  (`"tiktok"` / `"instagram"` / `"youtube"` / `"pinterest"` /
  `"facebook"`) — the Activity Hub + `epic-import-row-rich-detail`
  use this for labeling.
- Web URLs stay as `source_type="url"`; `detected_platform` is not
  set.
- `extract_recipe_task`'s existing social-URL branch keeps working as
  a defensive fallback (no behaviour change there — the primary
  decision is now upstream but the fallback still catches URLs the
  endpoint missed due to classifier drift, which is always possible
  since `_PLATFORM_PATTERNS` evolves).
- url_list imports are out of scope for this story — the AC in the
  epic explicitly scopes social detection to `source_type="url"`,
  and the url_list item creation loop is unchanged.

## Acceptance Criteria

1. `detect_platform()` runs inside `StartImport.execute` for
   `source_type == "url"` before the `ImportItem` is constructed.
2. Non-`WEB` platforms promote `source_type` to `"video"` on the item
   and populate `raw_data["detected_platform"]` with the platform
   enum's string value.
3. Web URLs: item keeps `source_type="url"`, and `raw_data` stays
   empty (no `detected_platform` key).
4. Existing `extract_recipe_task` social-URL check is untouched.
5. Unit tests cover all five supported platforms (happy URL variants
   from `_PLATFORM_PATTERNS`) plus the web default.
6. Endpoint tests cover TikTok promotion, Instagram promotion, and a
   web URL staying as `url`.
7. `npx nx run api:lint` + api:test pass on the sbf-5 surface.

## File List

- MODIFIED `services/api/src/api/v1/import_job/start_import.py` —
  url branch calls `detect_platform(params.url)`, sets
  `source_type` + `raw_data.detected_platform` accordingly.
- NEW `services/api/tests/test_url_classifier.py` —
  `TestDetectPlatform` with parametrized coverage of all 5 platforms
  + web default + `is_social_media_url` sanity check (21 tests).
- MODIFIED `services/api/tests/test_import.py` — added
  `TestStartImportSocialUrlRouting` (3 tests).
