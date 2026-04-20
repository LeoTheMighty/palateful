# Story efi-4 — Hoist `inferred_fields` on import responses + `POST /v1/import-items/{id}/corrections`

**Status:** done
**Epic:** epic-extractor-field-inference
**Depends on:** efi-3 (recipes.inferred_fields column + extract_recipe_task wiring)

## Scope

Client-facing surface for Review Import and the correction-log side
channel:

1. `GetImportItem` and `list_import_items` hoist `inferred_fields` from
   `parsed_recipe` to the response-root `ItemSummary` / detail object —
   same pattern the `confidence_score` hoist already uses. Always a
   list; legacy / absent / malformed → `[]`. Server-side allow-list
   filter at the edge so a malformed legacy row can't smuggle a bogus
   field name onto the API surface.
2. `POST /v1/import-items/{id}/corrections` — new audit endpoint. On a
   debounced field edit in Review Import, the client POSTs
   `{field, corrected}`. Server validates `field` is in
   `INFERABLE_FIELDS`, checks ownership, and writes one `error_logs`
   row with `service="audit"`, `error_type="InferredFieldCorrected"`,
   `import_item_id=item.id`, `user_id=caller.id`, and a JSON-encoded
   metadata payload `{field, original, corrected, was_inferred}`.

`list_import_jobs` is intentionally NOT touched — it's a job-level
response without per-item data. The epic's wording was aspirational;
the hoist only makes sense where per-item data lives.

## Implementation notes

- Both hoist helpers (`_extract_inferred_fields` in `get_import_item.py`
  and in `list_import_items.py`) are deliberate copies of the same
  allow-list-filter pattern. Kept local to each endpoint so the list
  path doesn't import from the detail module (matches the existing
  `_extract_confidence_fields` precedent).
- `SubmitCorrection` returns `success(data=..., status=204)` via the
  standard `Endpoint.handle_result` path. The `Response` body is
  intentionally empty — it's a side-channel write, not a data fetch.
- `error_logs.error_message` carries the full correction metadata as a
  sorted JSON blob (ErrorLog has no `metadata_json` column, so JSON in
  the string column is the cheapest path — matches the precedent set
  by other audit writes). Sorted keys keep downstream parsing
  deterministic.
- 403 short-circuits 404: the lookup runs first, then the ownership
  check. Unknown item → 404; known item under a different user → 403.
  `field not in INFERABLE_FIELDS` → 400 returned BEFORE the DB lookup
  so junk requests don't even touch the row.

## File list

- `services/api/src/api/v1/import_job/submit_correction.py` [NEW] — endpoint.
- `services/api/src/api/v1/import_job/__init__.py` [MODIFY] — export `SubmitCorrection`.
- `services/api/src/routers/v1/import_router.py` [MODIFY] — `POST /v1/import-items/{id}/corrections` route.
- `services/api/src/api/v1/import_job/get_import_item.py` [MODIFY] — `_extract_inferred_fields` helper + response root field.
- `services/api/src/api/v1/import_job/list_import_items.py` [MODIFY] — same helper + per-item hoist.
- `services/api/tests/test_import.py` [MODIFY] — `TestInferredFieldsHoist` (4 tests) + `TestSubmitCorrection` (6 tests).

## Acceptance criteria — coverage

| AC | How |
|----|-----|
| 1 | `_extract_inferred_fields` on both endpoints; response schemas gain `inferred_fields: list[str] = []`. Covered by `test_get_import_item_hoists_inferred_fields` + `test_list_import_items_hoists_inferred_fields` + `test_get_import_item_legacy_returns_empty` + `test_get_import_item_filters_non_allowlist_in_legacy_row`. |
| 2 | `submit_correction.py` — validates `field` against `INFERABLE_FIELDS`, writes the audit row with full metadata. Covered by `TestSubmitCorrection::test_happy_path_writes_audit_row`. |
| 3 | Endpoint does NOT call `self.database.update(item, ...)`. Covered by the implementation (no write paths) + `test_happy_path_writes_audit_row` only asserting on the ErrorLog row. |
| 4 | Happy / was-not-inferred / field-not-in-allow-list / wrong-user / missing-item paths all covered in `TestSubmitCorrection`. Plus `test_missing_parsed_recipe_still_logs` for the extraction-failed-mid-flight edge case. |
| 5 | New test cases exercise every branch; `inferred_fields` response fields are Pydantic-validated `list[str] = []` so the FastAPI path is hit end-to-end. |
| 6 | No new indexes added — `error_logs.(service, created_at)` covers the dashboard queries this endpoint feeds. |
