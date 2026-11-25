---
hash: shk101
type: dev
created: 2026-11-25T10:03:01-07:00
title: Server accepts the trigger and serves the ring
from: plan/plan-f89791-2026-11-25T09:02-shake-to-report.md
workstream: _devx/workstreams/shake-to-report
phase: 1
status: in-review
owner: claude-session-01Dd56uByrknr4rjyd7vPkxZ
branch: feat/dev-shk101
blocked_by: []
---

## Goal

The feedback context accepts `trigger` (`profile`, `shake`, absent) and `GET /v1/flags/perf` serves `shake_report` (`off`/`admins`/`everyone`) from a terraform-set `SHAKE_REPORT_RING`, default `admins`. First, because the merge is the deploy and shk102's client sends `trigger`.

## Acceptance criteria

- [x] E-6: `python3 tools/api-pytest-targeted.py tests/test_shake_flags_and_trigger.py` exits 0 from `services/api` (ring default and each value, invalid value fails settings, `shake`/`profile` stored, `wiggle` → 422 and no row).
- [x] `npx nx run api:test` green at 100%; `npx nx run api:lint` clean.
- [ ] CI's prod terraform plan shows one added environment entry on the API task definition and nothing else. *(Open: that plan only exists on the first `main` run. Read it there; expected is the env entry beside the per-deploy image-tag change.)*
- [x] `docs/PERFORMANCE_OPS.md` documents the ring and that a console task-definition flip lasts only until the next terraform-managed revision.

## Technical notes

- PRD: `_devx/workstreams/shake-to-report/prd/agent.md`; design: `_devx/workstreams/shake-to-report/design/agent.md`; plan: `_devx/workstreams/shake-to-report/plan/agent.md` (this phase's section is the full task and file list).
- P0 evals are locked by Gate 4 (`gate_status.red_eval_shas` in the plan spec); each wrapper also pins its Dart test, the runner and the harness, so an edited eval exits 3 (EVAL-TAMPERED). Make the code pass them; a genuinely wrong eval is `devx revise`, not an edit. `devx gate evals f89791 --verify` must stay PASS.
- Do not touch `admin-request-intake`'s files (its plan's Files lists, arq103's screen).
- Terraform: local CLI 1.4.2 vs state 1.16.3 invents phantom diffs; read the plan from CI.
- One-way once a client release sends `trigger` (plan Risks): never remove it from the server before shipping a client without it.

## Status log

- 2026-11-25T10:03 — emitted by `/devx-plan` RED stage for workstream f89791 (plan phase 1). Gate 4: PASS.
- 2026-11-25 — implemented on `feat/dev-shk101` (`db100860`), PR #134 into `feat/shake-report-workstream` (not `main`; not merged). E-6 targeted GREEN (53 passed across E-6 + perf flags + feedback + config); `npx nx run api:test` 2695 passed, 100.00%; `api:lint` clean; prod `terraform validate` + `fmt -check` pass offline, each with a negative control. Every new test fails on the base except the old-client regression guard; one `wiggle → 422` check that passed on base via `extra_forbidden` was tightened to `literal_error`. P0s E-1…E-4 re-run on this branch: all still RED (exit 1, controls pass), same markers as RED-report — the evals fake HTTP, so no server change reaches them. Added a terraform `validation` block beyond the plan's file list. `devx gate evals f89791 --verify` PASS.
