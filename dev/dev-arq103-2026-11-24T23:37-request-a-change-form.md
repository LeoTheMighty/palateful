---
hash: arq103
type: dev
created: 2026-11-24T23:37:00-07:00
title: Request-a-change form in the admin panel
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 3
status: ready
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
