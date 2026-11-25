---
hash: arq103
type: dev
created: 2026-11-24T23:37:00-07:00
title: Request-a-change form in the admin panel
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 3
status: in-review
owner: null
branch: feat/dev-arq103
blocked_by: [arq101]
---

## Goal

A "Request a change" dashboard tile and a three-field form that calls the create endpoint and shows the returned id8. Last in the vertical slice.

**External gate X-1:** merge only after the orchestrator bridge is installed, or requests pile up unseen.

## Acceptance criteria

- [ ] E-7: `app/test/features/admin/admin_dev_request_new_screen_test.dart` passes (one create call per submit; id8 shown; 403/422/429 rendered; no entry for a non-admin).
- [ ] `flutter analyze` clean in `app/`.
- [ ] After external gate X-1 is installed and this deploys: the E-8 walkthrough (`_devx/workstreams/admin-request-intake/evals/E-8_live_walkthrough.md`) passes and its Runs row is recorded.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- The admin area is web-only and redirects non-admins (`app/lib/core/router/app_router.dart:225-227`, `:633-638`).

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 3). Gate 4: PASS.
- 2026-11-25T09:13 — implemented by hand (not through `/devx`; no Phase 4 parallel review — self-review plus negative controls instead) on `feat/dev-arq103`, cut from the slice integration branch `feat/admin-request-slice` at `cbe332d3`, the only tree with the create endpoint. T3.1 `04bb3a25`, T3.2 `15e20d71`, T3.3 `7a023a56`, T3.4 `ce4032c3`; follow-ups `500d05a0` (the full run's one failure: `fixture_date_guard_test` refused a dated `created_at` fixture) and `491a294c` (control M19 survived: the gate test never paired a blank title with a valid body). E-7 (`app/test/features/admin/admin_dev_request_new_screen_test.dart`): 16/16, on the real `ApiClient` with only its HTTP adapter replaced, replaying 201/403/422/429 bodies captured from the real endpoint at `cbe332d3` through `devreq_harness` (throwaway database), and the real `appRouter` for the route cases. 21 negative controls (one mutation each, throwaway worktree) all turn it red on the intended case. Full `flutter test` at `500d05a0`: 1764 passed, exit 0 (`491a294c` changes only the E-7 file, re-run 16/16). `flutter analyze`: 0 errors, no issue in any changed file except two warnings in `admin_dashboard_screen.dart` that are on `cbe332d3` already. `flutter build web --release` OK. The CI grep guards in `flutter-test` exit 0. `devx gate evals 1e84ad --verify` PASS. Deviation from the plan: the tile uses `_buildNavTile` (now with an optional key) rather than a copy of `_buildFeedbackTile`, since there is no count to badge until Phase 5. **Not verified: CI** (the PR does not target `main`). **Not run: a browser session against a live API** (needs an Auth0 login). **Not done: T3.5 / E-8** — after X-1, Leo's. **Not merged**: gate X-1.
