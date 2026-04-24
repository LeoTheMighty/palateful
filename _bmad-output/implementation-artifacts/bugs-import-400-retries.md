# Story bugs-import-400-retries: Surface API 4xx error_code for triage

Status: done

## Story

As the production error-audit pipeline (`audit_errors.py`),
I want every API 4xx response to write a compact `error_logs` row and every
client-side `DioException` report to carry the server's structured
`error_code` + `error_message`,
so that triage (on the ground truth "which validator branch fired?") stops
requiring repro or log-grovelling.

## Context

`audit_errors.py` triage on 2026-04-24 surfaced an 86-event client-side
`DioException` cluster (all `status=400`, all one user, all `POST
/v1/recipe-books/ec9c957a-…/import`). Neither the client nor the server
currently writes any structured detail for a 4xx:

- The Flutter `_mirrorReportToBackend` copies `DioException.message` —
  which is generic Dio "validateStatus" boilerplate, not the server's
  structured `{error_code, error_message}` envelope.
- The API-side `ErrorTrackingMiddleware` only persists 5xx responses;
  `APIException` 4xx paths (and there are ~11 such branches in
  `start_import.py` alone) return their structured body but leave no
  durable row behind.

Result: `audit_errors.py --drill client:DioException` shows us 86 rows
that all say "status=400 POST /…/import" with no signal which branch
fired. The observability gap is what makes this /dev-worthy; actually
fixing the 400 is a separate, downstream task that unblocks once this
lands.

## Acceptance Criteria — all green

1. In `libraries/utils/utils/api/endpoint.py`, extend both `Endpoint.run`
   and `AsyncEndpoint.run` to persist a compact `error_logs` row on any
   caught `APIException` whose `status_code` is in `[400, 500)` **and**
   `ENVIRONMENT == "prod"`. Row fields:
   - `service="api"`, `error_type="APIException"`
   - `status_code`, `error_code` (both from the exception)
   - `method`, `path`, `user_id`, `request_id` (from `self.request` /
     `self.user`, same shape as the existing 5xx writer)
   - `error_message` = `e.detail` (clamped to 4000)
   - `stack_trace` = JSON blob `{"body_keys": [...]}` listing the
     Pydantic-explicitly-set field names on any positional/keyword
     Pydantic `BaseModel` arg passed to the endpoint — **names only,
     never values.** Empty-list payload is `null`.
2. Non-prod environments MUST NOT write 4xx rows (every 4xx unit test
   would otherwise flood the mock DB). Gate strictly on
   `utils.constants.ENVIRONMENT == "prod"` (not truthy, not `!= "test"`).
3. Async endpoints dispatch the write onto the existing
   `run_in_threadpool` path — the 4xx logger shares the same sync writer
   (same `ErrorLogSessionLocal` sub-pool aam-3 carved out), so pool
   exhaustion on the main async pool can never starve 4xx audit.
4. Any exception raised by the 4xx writer is swallowed — auditing must
   never fail a response. Matches the existing 5xx writer's contract.
5. In `app/lib/core/services/error_reporter.dart`,
   `_mirrorReportToBackend` parses `DioException.response.data` when it
   is a map and extracts `error_code` (int) + `error_message` (string)
   from the standard FastAPI failure envelope. Both surface in the
   mirror POST:
   - `error_message` string now reads `"{METHOD} {path} → {status}
     [code={error_code}]: {server error_message}"`. Falls back
     gracefully if either is missing (retains current behavior).
   - `extras["server.error_code"]` carries the int for
     `audit_errors.py` aggregate rollups.
6. Non-map response bodies (HTML error pages from a load balancer,
   arbitrary strings, null) must NOT blow up the reporter — the parse
   is purely defensive.
7. Tests:
   - `services/api/tests/test_endpoint_api_error_logging.py` — asserts
     (a) prod 4xx writes one row with expected columns, (b) non-prod
     does not write, (c) `body_keys` contains only Pydantic-set field
     names (verifies no values are persisted), (d) 5xx path stays
     unaffected, (e) writer swallows a DB failure.
   - `app/test/core/services/error_reporter_mirror_test.dart` — asserts
     that a DioException carrying a `{error_code, error_message}`
     payload produces a mirror POST whose `errorMessage` contains
     `code=` and the server detail, and whose `extras` carries
     `server.error_code`. Non-map bodies don't crash.
8. `npx nx run api:lint`, `npx nx run api:test`, `dart analyze
   lib/core/services/error_reporter.dart`, and `flutter test
   test/core/services/error_reporter_mirror_test.dart` are all green
   locally before commit.

## Key Files

- Modify: `libraries/utils/utils/api/endpoint.py`
- Modify: `app/lib/core/services/error_reporter.dart`
- Create: `services/api/tests/test_endpoint_api_error_logging.py`
- Create: `app/test/core/services/error_reporter_mirror_test.dart`

## Do NOT

- Add a new `error_logs` column. Body keys go in the existing
  `stack_trace` Text column as a JSON blob.
- Log request-body VALUES anywhere. URL-shape payloads can contain
  `?utm_source=auth_token` query strings.
- Add a client-side retry policy for 400s. This story is observability
  only; retry-or-not is a downstream decision once we see the real
  error_code distribution.
- Change the `ErrorLog` model, add migrations, or touch
  `error_tracking.py` (the middleware stays 5xx-only — the 4xx write
  point is `Endpoint.run`, which has the `APIException.code` in hand).

## QA Walkthrough

(emitted as `bugs-import-400-retries-qa-walkthrough.md` at story end.)
