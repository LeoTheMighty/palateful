---
hash: arq101
type: dev
created: 2026-11-24T23:37:00-07:00
title: Request storage and the create endpoint
from: plan/plan-1e84ad-2026-11-24T22:51-admin-request-intake.md
workstream: _devx/workstreams/admin-request-intake
phase: 1
status: in-review
owner: null
branch: feat/dev-arq101
blocked_by: []
---

## Goal

Add the `dev_requests` table (every status and both source columns from day one), the `DevRequest` model with its normalization and hash helpers, and `POST /v1/admin/dev-requests` with the 5-per-hour rate limit. First, because every other phase reads or writes this row. Vertical slice.

## Acceptance criteria

- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-3_operator_only.sh` exits 0 (EVAL-GREEN).
- [ ] `bash _devx/workstreams/admin-request-intake/evals/E-5_normalization.sh` exits 0 (EVAL-GREEN).
- [ ] E-6: `services/api/tests/test_dev_requests_rate_limit.py` passes (calls 1–5 → 201, call 6 → 429 with `retry_after_s`, another admin unaffected).
- [ ] `npx nx run api:test` green at 100% branch coverage; `npx nx run api:lint` clean; CI `migrate-test` applies the migration.
- [ ] The E-3 and E-5 lines are deleted from `tools/red-artifacts.txt` in the commit that turns them green.

## Technical notes

- PRD: `_devx/workstreams/admin-request-intake/prd/agent.md`; design: `_devx/workstreams/admin-request-intake/design/agent.md`; plan: `_devx/workstreams/admin-request-intake/plan/agent.md` (this phase's section is the full task list and file list).
- Contract evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals 1e84ad --verify` must stay PASS.
- Evals need a reachable Postgres: `docker compose up -d db` locally; CI's `test` job provides one.
- The merge is the deploy (`production` has 0 protection rules). Leo merges every PR by hand.
- Migration `down_revision` = the Alembic head when the phase starts (`idupbookname1` on 2026-11-24 — re-read it, do not trust this line).
- Rate-limit pattern: `services/api/src/api/v1/user/create_user_feedback.py:41-60`.

## Status log

- 2026-11-24T23:37 — emitted by `/devx-plan` RED stage for workstream 1e84ad (plan phase 1). Gate 4: PASS.
- 2026-11-25T00:45 — implemented by hand (not through `/devx`; no Phase 4 parallel review — a `/code-review high` was run on the branch instead) on `feat/dev-arq101`, stacked on `feat/admin-request-workstream`. E-3 and E-5: EVAL-GREEN through their own wrappers (8/8, 12/12), both previously RED for their recorded reason (no table; POST not routed); each also proven to go RED again under a targeted mutation (no `extra=forbid`, wrong status, no admin guard, no normalization, NFC for NFKC, `""` for a null done-when, no length limit). E-6 passes against a real Postgres. `npx nx run api:test` locally with CI's env: 2748 passed, 100.00%. Migration applied, `alembic check` clean, downgraded and re-applied on a throwaway database. **Not verified: CI** — `ci.yml` and `devx-ci.yml` run only on PRs into `main`, so this stacked PR gets no CI run. E-1, E-2, E-4 stay RED for Phase 2's reason (scripts / `bin/prod-script` forwarding), no longer for a missing table.
