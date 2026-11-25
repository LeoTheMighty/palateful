---
hash: arq106
type: dev
created: 2026-11-24T23:37:00-07:00
title: Pipeline progress fields in the write script
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 6
status: ready
owner: null
branch: feat/dev-arq106
blocked_by: [arq102, arq103]
---

## Goal

The widening edges of PRD FR-12 and their FR-17 arguments (`--workstream`, `--spec-hash`, `--pr`, `--detail`/`--gate`/`--count`), so the bridge can report scoping … shipped and "waiting on Leo". Widening.

**Starts only after E-8 passes.** Consumed by external gate X-2.

## Acceptance criteria

- [ ] E-11: `services/api/tests/test_dev_requests_pipeline_fields.py` passes.
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-4_transitions.sh` still exits 0 (it samples only edges no phase legalizes).
- [ ] `docs/HELPFUL_SCRIPTS.md` documents the new arguments.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- `--workstream` takes any devx slug (`^[a-z0-9][a-z0-9-]{0,49}$`), because routing fits items into ordinary workstreams.

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 6). Gate 4: PASS.
