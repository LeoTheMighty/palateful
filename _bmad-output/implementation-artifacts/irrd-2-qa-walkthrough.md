# QA Walkthrough — irrd-2: Backend telemetry endpoint + stage logging

**Story:** irrd-2-backend-import-item-telemetry-endpoint
**Epic:** epic-import-row-rich-detail
**Commit:** (pending — see `git log --oneline origin/main..HEAD`)

## Pre-flight (local)

- `alembic upgrade head` should add:
  - columns `error_logs.import_item_id`, `error_logs.stage`
  - partial index `ix_error_logs_import_item_created` (`WHERE import_item_id IS NOT NULL`)
- `alembic downgrade -1 && alembic upgrade head` must round-trip cleanly.

## Smoke test (curl / httpie)

After deploying a build with the new endpoint + at least one import-task
run that flows through `log_stage_transition`:

```bash
# Fetch the current user's import jobs, pick an item id
curl -s -H "Authorization: Bearer $TOKEN" \
  https://api.palateful.app/v1/import-jobs | jq '.data.items[0].items[0].id'

# Telemetry for that item
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.palateful.app/v1/import-items/$ITEM_ID/telemetry" | jq
```

Expected shape:

```json
{
  "item_id": "...",
  "stages": [
    { "stage": "parsed", "status": "ok", "started_at": null, "completed_at": "...",
      "duration_ms": null, "raw_output_preview": "1 cup flour\n...", "truncated": false },
    { "stage": "extracted", "status": "ok", "started_at": "...", "completed_at": "...",
      "duration_ms": 3000, "raw_output_preview": "{\n  \"name\": ...\n}", "truncated": false },
    { "stage": "matched", "status": "ok", "started_at": "...", "completed_at": "...",
      "duration_ms": 1200, "raw_output_preview": null, "truncated": false },
    { "stage": "created", "status": "pending", ... }
  ]
}
```

## Manual checklist

- [ ] Fetching an item you don't own returns **403** (not 500, not 404).
- [ ] Fetching a nonexistent item returns **404**.
- [ ] Fetching a brand-new item with no logs yet returns **200** with
      four `status: "pending"` entries.
- [ ] `parsed_preview` on a photo import has the OCR text (truncated at
      4096 chars with `truncated: true` if oversized).
- [ ] `extracted_preview` is valid JSON when truncated-false; it is the
      pretty-printed `parsed_recipe`.
- [ ] Tap the `parsed` preview in the Flutter caret (irrd-4/-5 when it
      lands) — it should render monospaced and scroll.
- [ ] Trigger a failed extraction (force-raise in `extract_recipe_task`)
      — telemetry shows `extracted.status = "failed"`, duration_ms
      present.
- [ ] Retry the failed item — `extracted.status` flips back to `ok` on
      next poll (the accumulator takes the latest terminal row).
- [ ] Legacy `error_logs` rows with `stage = NULL` do not appear in the
      telemetry response.

## AST-lint guarantee

`libraries/utils/test/test_stage_transition_enforcement.py` fails CI if
any module outside `libraries/utils/utils/logging/stage_logging.py`,
`.../tasks/import_tasks/`, or `.../tasks/parser_tasks/` emits
`"StageTransition"` as a literal. New stage log calls MUST route through
`log_stage_transition(…)`.

## Known deferrals

- **P95 < 300ms at 10k rows** — partial index serves the query plan, but
  a fixture-seeded timing assertion is deferred to a load-test story
  rather than baked into the unit suite (which runs on mocks).
- **`manual` awaiting-review reason** — the CHECK constraint allows it,
  no code path sets it yet. Follow-up when an admin-route manual-flag
  endpoint lands.
- **Cache invalidation from the Flutter side** — irrd-4's responsibility,
  not irrd-2's.
