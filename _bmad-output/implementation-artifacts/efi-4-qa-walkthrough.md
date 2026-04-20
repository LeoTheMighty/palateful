# efi-4 — QA walkthrough

API-surface expansion. Two changes: hoist `inferred_fields` onto the
Review Import responses, and add `POST /v1/import-items/{id}/corrections`
for user overrides. No migration, no worker path.

## Local checks

```bash
DATABASE_URL=sqlite:///nonexistent.db AUTH0_DOMAIN=test.auth0.com AUTH0_AUDIENCE=https://api.palateful.test \
  poetry run pytest services/api/tests/test_import.py -k "TestInferredFieldsHoist or TestSubmitCorrection" --no-cov
npx nx run api:lint       # my files clean; two pre-existing lint errors in list_import_items.py are parallel-agent pagination WIP.
```

Expected: 10 new efi-4 tests green; api:lint clean against my files only.

## Live curl sanity (requires dev server + a real import item)

```bash
# Hoist sanity: the field should always be present, list-typed.
curl -s ":API/v1/import-items/$ITEM_ID" -H "Authorization: Bearer $TOKEN" | jq .inferred_fields

# List-endpoint sanity: every item has the field.
curl -s ":API/v1/import-jobs/$JOB_ID/items" -H "Authorization: Bearer $TOKEN" \
  | jq '.items[] | {id, inferred_fields}'

# Happy path: submit a correction on an inferable field.
curl -sX POST ":API/v1/import-items/$ITEM_ID/corrections" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"field": "cook_time_minutes", "corrected": 45}' \
     -o /dev/null -w "%{http_code}\n"
# → 204

# Bad field → 400 + data.allowed
curl -sX POST ":API/v1/import-items/$ITEM_ID/corrections" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"field": "name", "corrected": "nope"}'
```

Check that a new row lands in `error_logs`:

```sql
SELECT service, error_type, import_item_id, error_message
  FROM error_logs
 WHERE service = 'audit' AND error_type = 'InferredFieldCorrected'
 ORDER BY created_at DESC
 LIMIT 5;
```
