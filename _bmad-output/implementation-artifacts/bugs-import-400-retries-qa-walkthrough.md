# QA Walkthrough — bugs-import-400-retries

Ship-gate checklist for the 4xx audit + Flutter ErrorCode surfacing
landed in `bugs-import-400-retries`. Run these once the build is on
prod (post-merge, post-`bin/prod-*-deploy`).

## 1. Prod 4xx → error_logs row (server-side verification)

Trigger a known-good 400 on prod as yourself (the easiest is the
duplicate-idempotency path that already fires the rate-limit branch),
then:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill api:APIException --window 1h --format json | head
```

**Expected:** at least one row with
- `status_code` in `[400, 499]`
- `error_code` populated (e.g. 37 for `INVALID_REQUEST`, 101 for
  `RECIPE_BOOK_ACCESS_DENIED`, 203 for `RATE_LIMITED`, …)
- `error_type == "APIException"`
- `method == "POST"`, `path` matches the request
- `stack_trace` is a short JSON blob shaped
  `{"body_keys": ["source_type", "url", ...]}` — **names only, never
  values**. Verify no URL fragments, raw_text content, or file names
  appear anywhere.

## 2. Non-prod skip (local / CI)

On a local dev session (or in CI) cause a 400 via the API. Confirm:

```bash
DATABASE_URL=<local-url> python services/api/scripts/audit_errors.py \
    --drill api:APIException --window 10m
```

**Expected:** no rows. The env-gate is `ENVIRONMENT == "prod"` strictly;
dev / test / staging should not pollute audit.

## 3. Flutter DioException mirror — server ErrorCode surfacing

Install the shipped build on a real device (not a simulator; mirror is
gated off in `kDebugMode`). Deliberately send a malformed import
(e.g. share the same URL twice fast to trip dedup, or a share that
exceeds `raw_text` limits). Then:

```bash
DATABASE_URL=<prod-url> python services/api/scripts/audit_errors.py \
    --drill client:DioException --window 10m --format json | head
```

**Expected:** the newest row's `error_message` now reads
`"POST /v1/... → 400 [code=37]: URL is required for url source type"`
(or similar — the point is the `[code=N]` and the server-supplied
detail are present, NOT Dio's generic validateStatus boilerplate).

## 4. Regression — existing 5xx path stays unchanged

Force a 500 (easiest in prod: hit an endpoint with a known transient
failure case, or run a single integration test locally that forces an
endpoint exception). Confirm:

- `service='api'` row with `error_type != "APIException"` (real
  exception class, e.g. `ValueError`, `IntegrityError`) still lands.
- `stack_trace` column contains a real Python traceback (not a JSON
  body_keys blob) — the 5xx writer path is untouched.

## 5. Writer-failure isolation (smoke)

Not user-runnable in prod, but verified in `test_writer_swallows_db_failure`:
the 4xx logger swallows every exception, so a pool-exhaustion or
schema-mismatch incident in `error_logs` can never fail a user's
request. Matches the 5xx writer's existing contract.

## 6. Non-map response bodies (Flutter)

Not user-runnable, but covered by `error_reporter_mirror_test.dart` —
the parse must not crash on HTML error pages from a load balancer,
null bodies, string bodies, or non-int `error_code` values. If any of
the regression tests in that file start failing on a future refactor,
fix forward before re-enabling the mirror — a crashing mirror recurses
into Crashlytics.

## Rollback

If a downstream bug surfaces (unexpected volume, PII leak, writer
recursion), revert these two commits in this order:

1. The story commit (touches `endpoint.py`, `error_reporter.dart`,
   tests, story files).
2. Any follow-on `chore(app): bump to …` pubspec commit.

Neither commit touches the DB schema or the ErrorLog model — revert is
pure code-level. The `error_logs.stack_trace` rows written by the new
path are harmless JSON blobs that will simply stop being produced.
