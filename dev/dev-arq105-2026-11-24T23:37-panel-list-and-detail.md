---
hash: arq105
type: dev
created: 2026-11-24T23:37:00-07:00
title: Panel list and detail screens
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 5
status: ready
owner: null
branch: feat/dev-arq105
blocked_by: [arq104]
---

## Goal

The admin list with a status chip per request and the two staleness hints, and the detail screen that replaces `show` as Leo's reading surface. Widening.

**Starts only after E-8 passes.**

## Acceptance criteria

- [ ] E-10: `app/test/features/admin/admin_dev_requests_list_screen_test.dart` passes (13 of 13 status chips; 15-minute hint boundary; 3-hour listener hint).
- [ ] `flutter analyze` clean.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- Shape: `AdminFeedbackScreen` (`app/lib/features/admin/admin_feedback_screen.dart:172`, `:232-234`). Hints compare against the response's `now`, not the device clock.

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 5). Gate 4: PASS.
