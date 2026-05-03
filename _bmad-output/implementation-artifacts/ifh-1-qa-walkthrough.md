# QA walkthrough — Story `ifh-1`

> Backend: request_id propagation + retryable classification on /import & /upload-url. No client-visible change yet — this story lays the contract that ifh-3 (iOS) and ifh-4 (Dart) will consume.

## Pre-flight

```bash
cd /path/to/palateful
git pull origin main
npx nx run api:test          # expect 2566 passing, 100% coverage
npx nx run api:lint          # expect "All checks passed!"
npx nx run utils:lint        # expect "All checks passed!"
```

## Manual checks (server contract)

### 1. Permanent failure surfaces `retryable: false`

```bash
# Spin up the local stack first (docker compose up).
# Token = any valid JWT for a test user.
TOKEN=...

curl -s -X POST http://localhost:8080/v1/recipe-books/no-such-book/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"url","url":"https://example.com/recipe"}' | jq
```

Expected (the user has no membership in `no-such-book`):

```json
{
  "error_code": 161,
  "error_message": "You don't have permission to import recipes to this book",
  "data": {},
  "retryable": false
}
```

`retryable` MUST be at the top level (not nested under `data`).

### 2. Transient failure surfaces `retryable: true`

```bash
# Saturate the rate-limiter then hit it once more.
for i in $(seq 1 31); do
  curl -s -X POST http://localhost:8080/v1/recipe-books/<your-book-id>/import \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"source_type\":\"url\",\"url\":\"https://example.com/r$i\"}" \
    -w "\nstatus=%{http_code}\n"
done
```

The 31st call returns `429` with body:

```json
{
  "error_code": 165,
  "error_message": "Too many imports (max 30/hour). Retry in <N>s.",
  "data": {"retry_after": "..."},
  "retryable": true
}
```

### 3. Successful path is unchanged

```bash
curl -s -X POST http://localhost:8080/v1/recipe-books/<your-book-id>/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"url","url":"https://example.com/test-1"}' | jq
```

Expected: `201` with the standard `StartImport.Response`. NO `retryable` key in the body (success bodies aren't classified).

### 4. Unrelated endpoints have unchanged wire shape

Hit any non-import 4xx — e.g. fetch a recipe you don't have access to:

```bash
curl -s -X GET http://localhost:8080/v1/recipes/<recipe-id-someone-else-owns> \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected: `error_code` + `error_message` + `data`. **No** `retryable` key. (Endpoints outside the import path haven't classified yet — wire-shape backwards-compat is intentional.)

## Server-side observability check (prod-only path)

To confirm the request_id propagation fix end-to-end you need a prod-mirror run, since `_log_api_error_to_db` is gated on `ENVIRONMENT=="prod"`:

```bash
# After deploy:
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
  --drill api:APIException --window 1h --format json --top 20 \
  | jq 'select(.path | startswith("/v1/recipe-books") and contains("/import")) | {path, error_code, request_id}' \
  | head -20
```

Expected: at least one row with non-null `request_id`. Pre-fix, every row from `/v1/recipe-books/.../import` had `request_id: null` (compounded triage during the 2026-05-03 audit). Post-fix, request_id is populated.

If desired, correlate with CloudWatch using that `request_id`:

```bash
bin/prod-logs --grep "<request_id-uuid>"
```

## Regressions to watch

- **Other routers' wire shape.** Every endpoint outside `import_router.py` should look exactly the same — no `retryable` key in any error body. Fast smoke: trigger a 4xx on `/v1/recipes/...`, `/v1/shopping-lists/...`, `/v1/meal-events/...` — all should return `{error_code, error_message, data}` only.
- **OBJECT_NOT_READY classification.** Force a 409 by POSTing an import with an `s3_key` for an object that hasn't propagated to S3 yet (or mock HeadObject 404). Body MUST include `retryable: true` — getting this wrong would cause iOS/Dart clients (after ifh-3/ifh-4 ship) to permanently fail an import that would have succeeded on retry.
- **DUPLICATE_IMPORT classification.** POST a second `/import` for an `s3_key` that already has an `ImportItem`. Body MUST include `retryable: false` — getting this wrong would cause clients to loop forever on a 409 the user already won.
- **Rate-limit `retry_after` still in `data`.** `data["retry_after"]` is independent of `retryable` — both must be present in a 429 body. Existing `retry_after` clients keep working.
- **Coverage.** `npx nx run api:test` must report 100.00%. ifh-1's audit-writer test patches `utils.constants.ENVIRONMENT` to `"prod"` to exercise the prod-only writer; if that test fails coverage drops to ~99.6%.

## Post-merge follow-ups

- `ifh-3` (iOS): Swift `parseErrorPayload` should learn to read top-level `retryable` (currently only reads `error_code` + `error_id`).
- `ifh-4` (Dart): `PendingImportsReconciler` should read top-level `retryable` and use it as the primary signal for backoff vs. permanent-fail (with the 4xx/5xx heuristic as fallback for older server responses).
- Outside this epic: a sweep to forward `Request` through all 25 remaining routers. The pattern is the trivial three-line change applied here. Belongs in a separate observability epic.
