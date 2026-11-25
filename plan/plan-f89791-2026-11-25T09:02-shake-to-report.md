---
hash: f89791
type: plan
created: 2026-11-25T09:02:07-07:00
title: Shake To Report
status: in-progress
stage: design
entered_at: prd
gate_status:
  prd_validated: true
  design_verified: false
  plan_verified: false
  evals_red: false
outcome:
  status: null
  measure_by: null
workstream: _devx/workstreams/shake-to-report
gate_verdicts:
  prd: PASS
---

## Goal

Shake-to-report for Palateful's iOS and Android app: a deliberate shake shows a small prompt; a tap opens the dev-request form for an admin (arq103's `/admin/dev-requests/new`, an external gate) and the existing feedback sheet for everyone else, recording the screen. Built so a false shake costs nothing, with a server-side rollout ring and a per-device switch. Artifacts live in `_devx/workstreams/shake-to-report/`.

## Status log

- 2026-11-25T09:02 — workstream scaffolded by `devx workstream new shake-to-report`.
- 2026-11-25T09:35 — prd stage: `devx gate prd f89791` → PASS (1 FAIL round: E-8 threshold had no numerals). Artifacts: `prd/agent.md`, `prd/human.md` (render lint 0 HARD), `expectations.md` (E-1…E-10; P0: E-1…E-4), `decisions/2026-11-25-separate-workstream.md`. Templates came from cherry-picking 87c0663e (admin-request-intake's template commit) so both branches add identical files; the first `devx workstream new` at c80d253 refused on the flat templates and still wrote a plan spec and three empty dirs, removed by hand. Critique skipped (thoroughness send-it). Outline not bootstrapped (dispatched run). Profile preflight: non-interactive, registry defaults, nothing recorded. Feasibility probe before pinning Verified-by: the real `PalatefulApp` boots signed-in in a widget test run from outside the `app/` package, and the sensors_plus channel can be faked.
