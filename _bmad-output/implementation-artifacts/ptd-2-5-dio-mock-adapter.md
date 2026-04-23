# Story ptd-2.5 — Dio mock adapter + auth bypass plumbing

**Epic:** epic-perf-debug-tooling
**Status:** in-progress → review → done
**Owner:** /dev
**Started:** 2026-04-23

## Context

ptd-2 needs a perf-audit integration harness that drives each top-level
screen and counts outbound GETs per endpoint. Running the harness against
a live backend would make the CI step slow, flaky (network), and tied to
seeded data. The budget only cares about **attempted** requests — what
code the app tried to issue — so the cleanest answer is to swap Dio's
`HttpClientAdapter` for a filesystem-backed mock that returns canned
responses from `tools/perf-audit-fixtures/` (or a sensible empty default
when no fixture exists).

This story carves out the shared infra so ptd-2 / ptd-3a / ptd-3b can
each focus on writing per-screen flows rather than re-inventing the
mock + counter.

Auth is handled via the existing `kE2EMode` compile-time flag
(`app/lib/core/config/environment.dart:5`, consumed throughout
`main.dart` and `error_reporter.dart:81,86`). Harness runs set
`E2E_MODE=true` via `--dart-define`, which makes the boot-path inject a
fixed `e2e-test-token`, skip Firebase / push registration, and call
`getMe()` against whatever adapter is installed on the Dio instance —
which will be the mock.

## Scope

- **Mock `HttpClientAdapter`** — resolves fixtures from
  `tools/perf-audit-fixtures/` keyed by method + path; falls back to a
  default `200 {}` (or `200 []` for collection-shaped GETs) when the
  fixture is absent. Zero network traffic.
- **Observing `Interceptor`** — counts attempted requests per
  `(method, redacted-path)` pair. Redaction collapses UUIDs and numeric
  ids to `:id` so `/v1/recipes/abc-123-...` and `/v1/recipes/def-456-...`
  both count against the `GET /v1/recipes/:id` budget entry.
- **Install helper** — single function that swaps `getIt<ApiClient>().dio`'s
  adapter + attaches the counter, returns the counter handle to the test.
- **Fixtures directory** with `README.md` documenting the format and a
  starter fixture for `GET /v1/users/me` (the only call that needs a
  non-default body for the boot path to succeed).
- **Smoke test** at `app/integration_test/perf_audit/00_harness_smoke_test.dart`
  exercising the mock + counter in isolation (no full app boot). Proves
  the harness plumbing works before ptd-2 layers on the home flow.

## Implementation

### New files

- `app/integration_test/perf_audit/harness.dart` — library with:
  - `PerfAuditRequest` (immutable entry: method + redacted path).
  - `PerfAuditRequestCounter extends Interceptor` with `requests`,
    `countsByEndpoint()`, `clear()`. Route redaction via a small regex
    for UUIDs + `int.tryParse` for numeric ids.
  - `PerfAuditMockAdapter implements HttpClientAdapter` — resolves
    fixtures from a configurable `fixtureDir` by slugifying
    `METHOD_path.json`; default body path for misses.
  - `installPerfAuditHarness({fixtureDir})` — static helper used by each
    per-screen test; returns the counter so the test can assert.

- `tools/perf-audit-fixtures/README.md` — format, refresh process, how to
  add a new fixture.
- `tools/perf-audit-fixtures/GET_v1_users_me.json` — minimum shape for
  `AuthService.updateOnboardingState` + `updateAdminState` to succeed
  during boot.

### New tests

- `app/integration_test/perf_audit/00_harness_smoke_test.dart` — builds a
  fresh `Dio`, installs the mock adapter + counter, exercises:
  - Fixture-backed response (`/v1/users/me` returns the committed
    fixture body).
  - Default-body fallback (`/v1/recipe-books` returns an empty list
    because no fixture exists).
  - Counter records attempted GETs, `countsByEndpoint` rolls up,
    `clear()` resets.
  - Route redaction (`/v1/recipes/abc-123-...` rolls into
    `GET /v1/recipes/:id`).

## Acceptance Criteria

- [x] (1) `tools/perf-audit-fixtures/` directory committed with README
  documenting fixture format + refresh process + one starter fixture.
- [x] (2) `perf_audit/harness.dart` installs the mock adapter + counter
  on an existing Dio; `kE2EMode=true` gate is external (set via
  `--dart-define` when running the harness suite) — the harness doesn't
  force it, just relies on main.dart's existing gate.
- [x] (3) Documented fixture-refresh process (README alongside fixtures;
  full ops-runbook entry lands in ptd-7's `docs/PERFORMANCE_OPS.md`).
- [x] (4) Harness smoke test proves mock + counter work end-to-end
  without hitting any real network (no `HttpClient` used at all).

## QA walkthrough

1. `cd app && flutter test integration_test/perf_audit/00_harness_smoke_test.dart`
   — all assertions green, no network traffic (test runs in <2s on a
   macOS dev box).
2. Inspect `tools/perf-audit-fixtures/` — README present, one starter
   fixture, format self-explanatory.
3. Grep `PerfAuditMockAdapter` across the repo — only referenced from
   `app/integration_test/perf_audit/**`. No production code path
   touches it.
4. Grep `tools/perf-audit-fixtures` across the repo — referenced only
   from the harness library + README. Nothing in `app/lib/` reads this
   directory at runtime.

## Non-goals (deferred)

- **Capturing real fixtures from dev backend** — only the one `users/me`
  fixture ships. Each per-screen test under ptd-3a / ptd-3b adds the
  fixtures it needs; CI doesn't require full parity with prod.
- **Response-body templating / parameterization** — fixtures are plain
  JSON files. Good enough for read-only perf-audit flows; we're not
  testing mutation responses.
- **Capture-mode fixture refresh** — the ops runbook documents `curl`
  against the dev backend. If/when flakiness demands automation, ptd-7
  adds a `tools/perf-audit-refresh-fixtures.sh` helper.

## File List

- `app/integration_test/perf_audit/harness.dart` (new)
- `app/integration_test/perf_audit/00_harness_smoke_test.dart` (new)
- `tools/perf-audit-fixtures/README.md` (new)
- `tools/perf-audit-fixtures/GET_v1_users_me.json` (new)
- `_bmad-output/implementation-artifacts/ptd-2-5-dio-mock-adapter.md` (new — this file)
