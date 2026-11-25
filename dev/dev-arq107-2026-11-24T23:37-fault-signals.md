---
hash: arq107
type: dev
created: 2026-11-24T23:37:00-07:00
title: Fault signals — faults and fault-adopt modes
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 7
status: ready
owner: null
branch: feat/dev-arq107
blocked_by: [arq106]
---

## Goal

`faults <window>`: server-side `error_logs` grouped by signature, at most 50 plus an overflow record, with no message, trace or raw-path text and nothing from `client` rows; and `fault-adopt <signature>`, the one call that returns a fault's samples, after adoption. Slice 2.

**Starts only after arq106 has landed and external gate X-2 runs.** Exercised live only by X-3.

## Acceptance criteria

- [ ] E-12: `services/api/tests/test_dev_requests_faults.py` passes (0 canaries; 50 + overflow; no `client`/`audit`; negative control via `fault-adopt`).
- [ ] E-13: `services/api/tests/test_dev_requests_fault_signature.py` passes.
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh` still exits 0.
- [ ] The two design assumptions are settled first and recorded in the status log: how the task obtains route templates, and the container-path → repo-path mapping for frames (one read-only `bin/prod-script` look at real `stack_trace` values).

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- PRD FR-18, FR-19; design § Assumptions and § Unresolved design questions.

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 7). Gate 4: PASS.
