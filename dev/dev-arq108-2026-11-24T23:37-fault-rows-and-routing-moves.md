---
hash: arq108
type: dev
created: 2026-11-24T23:37:00-07:00
title: Adopted faults as rows, and routing moves
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 8
status: ready
owner: null
branch: feat/dev-arq108
blocked_by: [arq107]
---

## Goal

`open-fault` (one open row per signature, enforced by a partial unique index) and `move` (compare-and-set on `workstream`), plus `metrics` gaining `faults_open` and `signatures_multi_workstream`. Slice 2, with routing.

Exercised live only by external gates X-3 (bridge faults) and X-4 (router).

## Acceptance criteria

- [ ] E-14: `services/api/tests/test_dev_requests_routing_writes.py` passes.
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-1_full_path.sh`, `…/E-2_containment_canary.sh` and `…/E-4_transitions.sh` still exit 0.
- [ ] `docs/HELPFUL_SCRIPTS.md` documents both writes.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- A devx split that only prepares children and leaves the partition to a human still works through `move` (PRD FR-22, external gate X-5).

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 8). Gate 4: PASS.
