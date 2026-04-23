# Perf audit fixtures

Committed JSON responses served by `PerfAuditMockAdapter`
(`app/integration_test/perf_audit/harness.dart`) during the perf-audit
integration test suite. The mock swaps Dio's `HttpClientAdapter` so
the suite never touches the network — which keeps the CI step fast,
hermetic, and independent of whatever happens to be seeded in the dev
backend on any given day.

## Format

One JSON file per request, keyed by method + path:

```
GET_v1_users_me.json
GET_v1_recipe-books.json
GET_v1_meals_upcoming.json
```

Slugification rules (`PerfAuditMockAdapter.fixtureKeyFor`):

1. Uppercase method: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`.
2. Path `/` → `_`.
3. Any other non-`[A-Za-z0-9_.-]` character → `-`.

Each file holds a single JSON object:

```json
{
  "status": 200,
  "body": {
    "id": "fixture-user-1",
    "email": "test@example.com"
  }
}
```

- `status` — HTTP status (defaults to `200` when omitted).
- `body` — response body (defaults to `[]` for GETs, `{}` for mutations
  when the file is absent entirely).

## Missing fixtures

`PerfAuditMockAdapter` falls back to `200 []` (for GETs) or `200 {}`
(for everything else) if no fixture file matches. That's the right
default for perf-audit flows: we don't care what the mock *serves*,
we care what the app *attempted*. Only commit a fixture when the
fallback isn't enough to let the flow progress.

In practice that's:

- `GET /v1/users/me` — must have `has_completed_onboarding` +
  `default_recipe_book_id` so `AuthService.updateOnboardingState`
  passes (see `app/lib/main.dart` E2E boot block).
- `GET /v1/recipes/:id` — detail-screen tests need enough shape for
  the screen to render past its shimmer.

Everything else can ride the default.

## Refresh process

Fixtures rot when the backend changes shape. When a flow breaks because
a field was renamed / dropped, re-capture the single fixture affected:

```bash
# 1. boot the dev stack
docker compose up api

# 2. grab an auth token (the dev-backend smoke-token is fine)
TOKEN=$(cat ~/.palateful-dev-token)

# 3. re-capture one endpoint
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/users/me \
  | jq '{status: 200, body: .}' \
  > tools/perf-audit-fixtures/GET_v1_users_me.json
```

Commit the refreshed fixture with a one-line PR note explaining what
backend change caused the drift. Full ops-runbook entry lives in
`docs/PERFORMANCE_OPS.md` (ptd-7).

## Why not capture everything up front?

Two reasons:

1. Every captured fixture is a freeze of that day's schema; the more
   we capture, the more we have to re-capture on every schema change.
2. The default-body fallback covers ~90% of flows (list screens, empty
   detail screens, "no data yet" states). Only the ~10% that require a
   specific shape need committed fixtures, and those are the ones that
   benefit from being reviewable in PRs.

Start with the default; add a fixture the first time a test fails
because the default wasn't enough.
