<!-- refined via party-mode 2026-04-23 -->

# Epic: Performance — Debug Tooling & CI Regression Guard

## Overview

Once `epic-perf-frontend-fetch-minimization` closes the current tail and `epic-perf-client-analytics` ships the observability backbone, the work that rots fastest is **the audit itself**. Without tooling, six months from now a new feature will quietly re-introduce duplicate `getRecipeBooks()` calls, a forgotten screen will grow a new polling loop, and someone will drop a fresh `Image.network(` on a hot tile. The audit will need to be re-run from scratch.

This epic ships three durable tools so perf stays measurable and regressions get caught at PR time, not after the fact:

1. **In-app debug perf overlay** (`kDebugMode` only) — floating widget listing the last N HTTP requests with durations + status codes, toggleable via long-press on a debug trigger. Lets Leo self-audit a flow in the simulator without opening Chrome DevTools.
2. **`bin/perf-audit` repeatable audit command** — a Patrol-based Flutter integration harness that drives every top-level screen (Home, Books, Recipe detail, Activity Hub, Meals, Calendar, Profile, Search, Cook mode entry) through a canonical flow and records the number of HTTP GETs + their endpoints. Two modes: `capture` (writes observed counts to a budget YAML) and `assert` (fails if observed counts exceed the budget). The budget YAML is committed.
3. **CI regression guard** — new GitHub Actions step runs `bin/perf-audit --assert` on every PR. Adding a duplicate fetch = red build. Extending `analyze_latency.py --regression-hunt --section client` so client-side p95 shifts > 1.5× baseline get the same treatment as server-side.

The end state: the perf audit isn't a one-time effort; it's an ongoing CI invariant. Budgets are committed, visible in PRs, and explicit when someone needs to raise one intentionally.

## Goal

- A developer opening the simulator in debug mode can long-press a corner of the home screen and immediately see every HTTP request + duration fired during the flow. No browser needed.
- Running `bin/perf-audit` on any branch produces a diff table: (screen) × (current fetch count) × (budget) × (delta). Green / yellow / red by threshold.
- CI fails a PR that adds a duplicate `getRecipeBooks()` call anywhere, because the per-screen budget for every affected screen tightens by one.
- `analyze_latency.py --regression-hunt --section client` flags a client-side p95 regression alongside the existing server-side one. Incident response runs the same command for both.
- Adjusting a budget is a two-line diff to `tools/perf-budgets.yaml` with a PR-description rationale — not a hidden tribal-knowledge handoff.

## End-User Flow

*Primary users: Leo (as developer) + Leo (as reviewer).*

1. **Developer flow — local audit.** Leo finishes a feature, runs the app in the simulator, long-presses the top-left corner of the home screen. A translucent overlay appears showing the last 20 HTTP requests with durations. He navigates through his feature; he sees exactly how many round-trips it issued. If anything looks off, he fixes it before opening the PR.
2. **Developer flow — per-screen budget check.** Leo runs `bin/perf-audit` locally before pushing. The tool spins up the Flutter integration harness, drives each top-level screen, prints a diff table: `Home: 4/5 (OK) • Activity Hub: 7/5 (FAIL: +2 calls)`. He knows exactly where the regression lives without re-reading his own diff.
3. **PR flow — CI guard.** Leo opens a PR. GitHub Actions runs `bin/perf-audit --assert`. The job fails. The PR comment (via GitHub job summary) shows the offending screens + delta. Leo clicks through, sees his new feature added a redundant `getRecipe()` on home's recent-cooked section, fixes it, re-pushes. Green.
4. **Operator flow — regression hunt.** 48 hours after a release, Leo runs `analyze_latency.py --regression-hunt --section all`. The output flags Home screen's client-side route-paint p95 jumped 1.8× baseline. He knows the regression is real and client-side within 30 seconds of opening his terminal.
5. **Budget maintenance flow — intentional raise.** Leo adds a legitimately necessary new fetch to Recipe Detail (e.g., a new sharing feature that requires a sibling call). The CI guard fails. Leo bumps `recipe_detail: 6 → 7` in `tools/perf-budgets.yaml`, writes a PR-description note `"Added shareable-link fetch; legitimately +1 call"`. PR reviewer sees the budget delta in the diff and can challenge or accept.

## Frontend Changes

### Debug overlay

- **New** `app/lib/core/debug/perf_overlay.dart` — `kDebugMode`-gated `Widget` wrapping `MaterialApp` (or inserted at the `Scaffold` level). Long-press on a 30x30 corner hit-zone toggles visibility. Overlay renders the last N=20 HTTP requests (method + path + status + duration) sorted by most recent. Updates in real time.
- **New** `app/lib/core/debug/perf_request_log.dart` — ring buffer (20-entry) subscribed to the Dio interceptor events emitted by `cla-6` (from `epic-perf-client-analytics`). Zero wire when not in debug.
- **Modify** `app/lib/main.dart` — conditionally wrap root widget with the overlay under `if (kDebugMode)` check.

### Perf audit harness

- **New** `app/integration_test/perf_audit/` directory containing one `*_test.dart` per screen (Home, Books, Recipe detail, Activity Hub, Meals, Calendar, Profile, Search, Cook mode entry). Each test uses the existing `patrol` harness (confirm Patrol is pre-installed in CI per Flutter matrix; if not, story `ptd-2` adds it).
- **New** `app/integration_test/perf_audit/harness.dart` — shared setup. Installs an observing Dio interceptor that counts GETs per screen, groups by endpoint pattern. Each test has a canonical flow (e.g., Home test: cold start → render → tap a recipe card → back; asserts counts).
- **New** `tools/perf-audit` (shell script) — wraps `flutter test integration_test/perf_audit/` with env vars `PERF_AUDIT_MODE={capture|assert}` and `PERF_AUDIT_BUDGET_FILE=tools/perf-budgets.yaml`. Capture mode writes observed counts; assert mode compares observed vs budget and exits non-zero on excess.
- **New** `tools/perf-budgets.yaml` — committed budget file. Schema:
  ```yaml
  screens:
    home:
      max_gets: 4
      endpoints:
        GET /v1/recipe-books: 1
        GET /v1/favorites: 1
        GET /v1/meals: 1
        GET /v1/recipes/recent: 1
    activity_hub:
      max_gets: 2
      endpoints:
        GET /v1/activities: 1
        GET /v1/import-jobs: 1
    # ... per screen
  ```
  First commit populates from the post-ffm baseline (epic-perf-frontend-fetch-minimization).

### Analyze-latency regression hunt

- **Modify** `services/api/scripts/analyze_latency.py` — extend `--regression-hunt` to cover `--section client`. Same logic: recent 24h p95 > 1.5× baseline (7-to-30d p95). Prints a unified table when combined with `--section all`.

## Backend Changes

- **None beyond the `analyze_latency.py` extension.** No new tables, no new endpoints. Regression detection runs from existing `client_latencies` (from `epic-perf-client-analytics`) + `request_latencies`.

## Infrastructure Changes

- **New GitHub Actions step** in the existing Flutter CI workflow — runs `bin/perf-audit --assert` after unit tests pass, before build. Caches Patrol runners via the existing Flutter cache. Adds ~3 minutes to CI time (budget conservative).
- **No new secrets, no terraform, no new env vars.**
- **Documentation** addition to `docs/PERFORMANCE_OPS.md` (or create): how to run `bin/perf-audit` locally, how to update budgets with rationale, how to read `analyze_latency.py --regression-hunt --section all` output.

## Design Principles (refined via party-mode 2026-04-23)

- **Invariants in code, not in tribal knowledge.** Every guarantee gets a CI check, a committed budget, or an allowlist file with reviewer sign-off.
- **Reuse, don't import.** Before adding a dep (Patrol, labeler action), check the repo for existing primitives. `integration_test` + `app/integration_test/helpers.dart` + `kE2EMode` (already in `app/lib/core/services/error_reporter.dart:81,86`) cover 80% of what Patrol would give us.
- **Budgets are readable, raisable, and reviewed.** `tools/perf-budgets.yaml` is the ceiling; `tools/perf-budget-waivers.txt` (mirrors `tools/silent-catch-allowlist.txt` format: `screen:endpoint:rationale`) is the one-line exemption list. Both diff-visible, both required for any raise.
- **Grace before strict.** New CI guard starts in warn-mode for 14 days (prints diff to job summary, doesn't fail). Strict mode flips via `PERF_AUDIT_STRICT=1` after the grace window.
- **Debug-only is compile-out, not runtime-check.** `kDebugMode` gate everywhere; release-build artifact grep verifies zero leakage in smoke test.
- **Zero cost in release, bounded cost in CI.** `paths: [app/**]` filter + PR-only triggers (not on `main` pushes) + shared Flutter cache. Budget: <5 min added per PR, <15 min/day total CI time.
- **Mirror precedents.** Silent-catch allowlist shape, `helpers.dart` test primitives, `analyze_latency.py` flag structure — new tooling echoes existing tooling so ops muscle memory transfers.
- **Client perf is noisier than server perf.** Threshold 2.0× (not 1.5×); `--min-samples 50` default for `--section client`. Same 7-to-30d baseline window as server.
- **The harness itself has a test.** Self-regression fixture in CI proves the assert logic still fails when it should. Tests for the test.
- **One change, one file-set, one reviewer signal.** Budget raise = budget YAML edit + waiver line + PR description rationale + auto-applied `perf-budget-change` label via `actions/labeler`. Reviewer has four independent cues.
- **Ride the analytics pipeline.** Don't build parallel telemetry; `--regression-hunt` reads `client_latencies` directly.

## File Structure

```
# Flutter — debug overlay
app/lib/core/debug/perf_overlay.dart                                  (new — kDebugMode-gated overlay widget)
app/lib/core/debug/perf_request_log.dart                              (new — ring buffer)
app/lib/main.dart                                                     (modify — conditionally wrap with overlay)

# Flutter — perf audit harness
app/integration_test/perf_audit/harness.dart                          (new — observing interceptor, shared setup)
app/integration_test/perf_audit/home_test.dart                        (new)
app/integration_test/perf_audit/recipe_books_test.dart                (new)
app/integration_test/perf_audit/recipe_detail_test.dart               (new)
app/integration_test/perf_audit/activity_hub_test.dart                (new)
app/integration_test/perf_audit/meals_test.dart                       (new)
app/integration_test/perf_audit/calendar_test.dart                    (new)
app/integration_test/perf_audit/profile_test.dart                     (new)
app/integration_test/perf_audit/search_test.dart                      (new)
app/integration_test/perf_audit/cook_mode_entry_test.dart             (new)

# Tooling
tools/perf-audit                                                      (new — shell script wrapper)
tools/perf-budgets.yaml                                               (new — per-screen budgets)
tools/perf-audit-diff.py                                              (new — helper: compares observed vs budget, emits GitHub job summary)

# Backend
services/api/scripts/analyze_latency.py                               (modify — regression-hunt on --section client + all)

# CI
.github/workflows/ci.yml                                              (modify — add perf-audit step)

# Docs
docs/PERFORMANCE_OPS.md                                               (new or modify — ops runbook)
```

## Story List (draft — ACs firmed up per-story)

### ptd-1 — Debug perf overlay (Profile avatar long-press)
**Hit-zone locked:** long-press on the Profile avatar — visible on every top-level screen (not just Home), no existing `onLongPress` conflict found via grep on `features/recipes/home/`.
**Buffer vs display:** buffer holds 100 entries; overlay displays 20 with internal scroll for the remainder.
**AC:** (1) `perf_overlay.dart` renders under `kDebugMode` only; (2) long-press on Profile avatar toggles visibility from any top-level screen; (3) overlay shows method + path + status + duration, scrollable, last 100 retained; (4) overlay updates in real time (subscribed to Dio interceptor events from `cla-6`); (5) release-build smoke test confirms overlay compiled out (`grep -r 'perf_overlay' build/app/outputs/` returns zero); (6) manual QA: navigate a flow in debug, confirm overlay shows expected requests.

### ptd-2 — Perf audit harness skeleton + home test (`integration_test`, no Patrol)
**Locked:** `patrol` is NOT added. The repo uses `integration_test` + `app/integration_test/helpers.dart` + `app/test_driver/integration_test.dart` (already present). Grep confirms no Patrol in `pubspec.yaml` or `Podfile.lock`; adding it = native-runner wiring on two platforms = out of scope.
**AC:** (1) `app/integration_test/perf_audit/harness.dart` provides an observing Dio interceptor shared across tests; (2) reuses `helpers.dart` primitives (`settle()`, `waitFor()`); (3) `08_perf_audit_home_test.dart` drives cold start → render → tap recipe card → back flow; (4) CSV-style per-endpoint count emitted at test end; (5) passing locally: `flutter test integration_test/perf_audit/08_perf_audit_home_test.dart`; (6) fails cleanly if endpoint count changes without budget update.

### ptd-2.5 — Dio mock adapter + auth bypass for perf tests
**New story carved out from ptd-2 / ptd-3.** Shared non-trivial infra before screen rollout.
**Locked:** tests hit a mocked `HttpClientAdapter` (counts *attempted* GETs — which is what the budget cares about), not live backend. Auth uses existing `kE2EMode` bypass flag (`error_reporter.dart:81,86` precedent).
**AC:** (1) `tools/perf-audit-fixtures/` directory with JSON responses captured once from dev backend; (2) `perf_audit/harness.dart` installs the mock adapter + `kE2EMode=true` gate; (3) documented fixture-refresh process in `docs/PERFORMANCE_OPS.md` (when fixtures go stale, re-capture); (4) harness test exercises the mock end-to-end without hitting any real network.

### ptd-3a — Per-screen test rollout — first 4 (books, recipe_detail, activity_hub, meals)
**Split out of original ptd-3** to parallelize + let the first batch iterate before the second ships.
**AC:** (1) four test files under `app/integration_test/perf_audit/`: `09_perf_audit_books_test.dart`, `10_perf_audit_recipe_detail_test.dart`, `11_perf_audit_activity_hub_test.dart`, `12_perf_audit_meals_test.dart`; (2) each has canonical flow documented in test-file header comment; (3) all five tests (incl. ptd-2's home) pass locally; (4) all runtimes <30s each; (5) no flaky tests (10 consecutive local runs green).

### ptd-3b — Per-screen test rollout — remaining 4 (calendar, profile, search, cook_mode_entry)
**AC:** (1) four test files: `13_perf_audit_calendar_test.dart`, `14_perf_audit_profile_test.dart`, `15_perf_audit_search_test.dart`, `16_perf_audit_cook_mode_entry_test.dart`; (2) canonical flows documented; (3) all 9 perf tests pass locally (covering ptd-2 + ptd-3a + ptd-3b); (4) full suite runs <5 min on CI; (5) 10 consecutive CI runs green on static branch.

### ptd-4 — `tools/perf-audit` + `tools/perf-budgets.yaml` + capture/assert modes
**AC:** (1) shell script wraps `flutter test integration_test/perf_audit/` with capture/assert modes; (2) capture writes observed counts to yaml; (3) assert compares observed vs budget, exits 0 if all within, exits 1 if any exceed, prints per-screen diff; (4) initial `tools/perf-budgets.yaml` populated from post-ffm baseline (committed with the epic); (5) `docs/PERFORMANCE_OPS.md` explains how to run + update budgets; (6) running `bin/perf-audit --capture` locally produces the same yaml as committed (idempotency check).

### ptd-4.5 — Budget waiver file + grep guard
**New story spawned by party-mode.** Mirrors the `silent-catch-allowlist.txt` / `no-silent-catch-check.sh` pattern exactly.
**AC:** (1) `tools/perf-budget-waivers.txt` committed with format `screen:endpoint:rationale` (one per line); (2) `tools/no-perf-budget-waiver-check.sh` fails if any `tools/perf-budgets.yaml` entry exceeds its default without a matching waiver line; (3) grep guard wired into CI alongside silent-catch check; (4) reviewer sign-off required in PR description (convention; not automated).

### ptd-5 — CI regression guard (warn-mode → strict)
**Locked rollout:** warn-mode for 14 days (prints diff, doesn't fail). Strict mode flips via `PERF_AUDIT_STRICT=1` env var after grace window. `paths: [app/**]` filter; PR-only (not on `main` pushes).
**AC:** (1) new step in `.github/workflows/ci.yml` runs `bin/perf-audit --assert` on PRs only, gated on `paths: [app/**]`; (2) step cached using existing Flutter CI cache; (3) warn-mode for 14 days post-merge then strict (doc comment with grace-window expiry date); (4) synthetic PR that adds a redundant `apiClient.getRecipeBooks()` to home triggers CI red after strict flip; (5) CI time delta documented (<5 min); (6) GitHub job summary shows per-screen diff always; (7) `actions/labeler` auto-applies `perf-budget-change` label when `tools/perf-budgets.yaml` is in diff; (8) retry-once policy on harness flake; 3 consecutive flakes quarantines the test via `tools/perf-audit-quarantine.txt`.

### ptd-6 — `analyze_latency.py --regression-hunt --section client|all`
**Locked thresholds:** 2.0× baseline (not 1.5×) for client — noisier than server. `--min-samples 50` default for client section. Baseline window 7-to-30d (same as server).
**Hard-depends on** `cla-1a` (client_latencies table must exist).
**AC:** (1) script accepts `--regression-hunt` alongside `--section client` or `--section all`; (2) client mode applies 2.0× baseline rule to `client_latencies.duration_ms` grouped by `(type, route)` pairs; (3) `--min-samples` flag overridable, defaults 5 (server) / 50 (client); (4) `all` mode prints unified table flagging both server and client regressions; (5) tests pin detection logic + table format + threshold correctness; (6) docs snippet in `docs/PERFORMANCE_OPS.md`.

### ptd-7 — `docs/PERFORMANCE_OPS.md` ops runbook
**AC:** (1) doc covers: how to run `bin/perf-audit` locally, how to update budgets + add a waiver line, how to read `analyze_latency.py` output (server + client + `--regression-hunt`), how the debug overlay works, where client analytics live (`client_latencies` table, `/admin/metrics` Client tab), how to refresh `tools/perf-audit-fixtures/`, how to quarantine a flaky harness test; (2) links to `cla-*` + `ffm-*` story files for cross-reference; (3) reviewer-sanity-checked by a round-trip read — can someone unfamiliar with the tooling follow it without asking questions.

### ptd-8 — Self-test: synthetic regression fixture
**New story spawned by party-mode.** Tests the test.
**AC:** (1) `tools/perf-audit-test-fixtures/regression.yaml` is a synthetic budget with one screen over-budget; (2) CI runs `bin/perf-audit --assert --budget=regression.yaml` and expects non-zero exit; (3) regression-detection logic broken by a bad refactor produces CI fail on the self-test; (4) documented in `docs/PERFORMANCE_OPS.md`.

## Dependencies

- **Soft depends on `epic-perf-client-analytics`** — `ptd-1` reads events from the Dio interceptor added in `cla-6`. If client-analytics hasn't shipped, `ptd-1` can still work with a locally-defined interceptor (≈30 lines), but it's cleaner to share. `ptd-6` reads `client_latencies` directly — hard dependency on `cla-1` landing first.
- **Soft depends on `epic-perf-frontend-fetch-minimization`** — the initial `tools/perf-budgets.yaml` baseline should reflect the *post-ffm* per-screen count. Budgets set pre-ffm would lock in the current bad state. Landing ffm first gives us the clean baseline to anchor to.
- **External dependency**: `patrol` flutter test package (confirm present in existing CI matrix; add as a story if missing).

## Open Questions for the User (post-party-mode)

1. **Warn-mode grace window: 14 days** default. Stricter (7 days) if user wants faster enforcement, or looser (30 days) to let budgets stabilize. Recommendation: 14.
2. **Overlay hit-zone.** Locked in party-mode as Profile avatar long-press. Alternative: shake gesture (iOS-native, Android needs sensor code). Recommendation: keep avatar long-press.
3. **Self-test story (`ptd-8`).** Worth the half-day, or trust manual verification in `ptd-5` AC4 (synthetic redundant-call PR)? Recommendation: keep it — tests-for-the-test catches regressions in the assert logic itself, which is important infrastructure.
4. **Budget-waiver file format.** Flat `screen:endpoint:rationale` text (matches silent-catch precedent) or structured YAML entries inside `perf-budgets.yaml` itself? Recommendation: flat text — precedent wins, fewer merge-conflict surfaces.
5. **Should `ptd-5` also post the perf diff as a PR comment** (via `actions/github-script`), not just job summary? Reviewer eyeballs land on comments more reliably than job summaries. Recommendation: yes, PR comment.
6. **CI runs on `main` push too, or only PRs?** Current locked decision: PRs only + `paths: [app/**]`. Main-branch run would catch drift if someone force-pushes or bypasses review. Recommendation: PR-only for cost containment; revisit if we ever bypass.
