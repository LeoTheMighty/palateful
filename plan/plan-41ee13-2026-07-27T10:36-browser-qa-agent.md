---
hash: 41ee13
type: plan
created: 2026-07-27T10:36:58-06:00
title: Browser Qa Agent
status: in-progress
stage: red
entered_at: prd
gate_status:
  prd_validated: true
  design_verified: true
  plan_verified: true
  evals_red: false
outcome:
  status: null
  measure_by: null
workstream: _devx/workstreams/browser-qa-agent
gate_verdicts:
  prd: PASS
  design: PASS
  plan: CONCERNS
  evals: null
---

## Goal

Workstream 'Browser Qa Agent' — PRD stage next. Artifacts live in `_devx/workstreams/browser-qa-agent/`.

## Status log

- 2026-07-27T10:36 — workstream scaffolded by `devx workstream new browser-qa-agent`.
- 2026-07-27 — PRD stage: research fan-out (3 Explore agents: QA infra, browser/e2e, engine seams), scoping interview locked hybrid driver + both-repos-palateful-first + 4 QA depths; wrote `_devx/workstreams/browser-qa-agent/prd.md`, `expectations.md` (E-1..E-6), `decisions/2026-07-27-hybrid-qa-driver.md` (narrow revision of framework QA.md 2026-04-23 driver ban; propagation tracked as FR-7). `devx gate prd 41ee13` → FAIL (E-4/E-6 Verified-by vague) → retargeted to `evals/E-4_*.md`/`evals/E-6_*.md` → PASS. Stage → design.
- 2026-07-27 — Design stage: user resolved both PRD open questions (e2e local-only; FR-5 direct to devx main) + re-confirmed Claude-in-Chrome driver. Grounding fan-out (3 Explore agents: e2e harness, devx engine internals, runner/walkthrough idioms) surfaced 3 latent defects folded into the design: E2E auth bypass dormant (`ENVIRONMENT` unset, `services/api/src/dependencies.py:109`), migrator-test/api DB mismatch (`test` vs `palateful`), `qa.browser_harness` schema enum lacks `claude-in-chrome`. Wrote `_devx/workstreams/browser-qa-agent/design.md`. `devx gate coverage 41ee13 --table …` → CONCERNS (UC-5/FR-8 persona rows partial) → persona-seeding protocol + migration step 4 added → `devx revise --touched design.md` → re-gate → PASS (25/25 ✅, report `decisions/2026-07-27-design-verify.md`). Stage → plan.
- 2026-07-27 — Plan stage: closed the deferred design question (`writeEngineTemplates` runs on init upgrade, `init-upgrade.ts:688` — template installs; no fallback). Drafted `_devx/workstreams/browser-qa-agent/plan.md` (7 phases; 1∥2∥3, 4→5→6→7). Critique pass (4 lens subagents: pm/architect/dev/qa; findings grep-verified) applied 17 findings — headline: RED-stage prerequisites hoist (`projects:` block + all 6 eval artifacts author at RED, phases only re-run), 4th latent defect found (`API_BASE_URL` defaults to prod — every browser launch now pins `http://localhost:8000`), E-1 asserts on dry-run JSON (prose verdicts never appear there), `INFRA:` sentinel discipline (gate can't distinguish exit 2), E-5 wrapper/demo split, hmp-5 flow renamed into the glob (population 8) — record `decisions/2026-07-27-plan-critique.md`. Coverage judge → `devx gate coverage 41ee13 --table …` → CONCERNS (E-5 partial: right-reason-by-substitution caveat; P0 floor passed), report `decisions/2026-07-27-plan-verify.md`. plan_verified ✓, stage → red.
