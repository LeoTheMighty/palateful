---
hash: arq102
type: dev
created: 2026-11-24T23:37:00-07:00
title: Operator channel — prod-script arguments, read and write scripts
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 2
status: ready
owner: null
branch: feat/dev-arq102
blocked_by: [arq101]
---

## Goal

Teach `bin/prod-script` to forward arguments, and add `services/api/scripts/dev_requests_read.py` (`poll`, `adopt`, `show`, `metrics`) and `services/api/scripts/dev_requests_write.py` (`transition`, slice edges only) speaking the `DEVREQ1` record protocol. This is the contract the orchestrator bridge is built against. Vertical slice; the riskiest phase (every ops session uses `bin/prod-script`).

## Acceptance criteria

- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-1_full_path.sh` exits 0.
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-2_containment_canary.sh` exits 0.
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-4_transitions.sh` exits 0.
- [ ] Both scripts import only the standard library, SQLAlchemy and `utils.constants` (asserted by E-1).
- [ ] After deploy, one read-only `bin/prod-script services/api/scripts/dev_requests_read.py poll` from Leo's plain terminal ends with `ok: true`.
- [ ] `docs/HELPFUL_SCRIPTS.md` and the CLAUDE.md Ops Scripts section document both scripts and the argument form.
- [ ] The E-1, E-2 and E-4 lines are deleted from `tools/red-artifacts.txt` in the commit that turns them green.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- No `from __future__` in either script (`docs/HELPFUL_SCRIPTS.md:20-22`).
- Scripts take their URL from `utils.constants.DATABASE_URL`, never `os.environ["DATABASE_URL"]` (prod tasks set `DB_*`).
- Widening edges stay `illegal_transition` until arq106.

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 2). Gate 4: PASS.
