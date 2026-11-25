---
hash: arq104
type: dev
created: 2026-11-24T23:37:00-07:00
title: List, detail and cancel endpoints
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 4
status: ready
owner: null
branch: feat/dev-arq104
blocked_by: [arq102, arq103]
---

## Goal

`GET /v1/admin/dev-requests` (no body), `GET /v1/admin/dev-requests/{id}` (the one route returning body and done-when) and `POST /v1/admin/dev-requests/{id}/cancel` (submitter only, before adoption). Widening.

**Starts only after E-8 passes** (Leo's sequencing: the slice works live, then widen).

## Acceptance criteria

- [ ] E-9: `services/api/tests/test_dev_requests_list_cancel.py` passes.
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh` still exits 0 (its allowlist names exactly these routes).
- [ ] `npx nx run api:test` green at 100%.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- Shape: `ListFeedback` (`services/api/src/api/v1/admin/list_feedback.py:26-58`). The list response carries the server's `now`.

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 4). Gate 4: PASS.
