---
hash: 462355
type: plan
created: 2026-07-27T10:51:32-06:00
title: Rotation Self Heal
status: in-progress
stage: plan
entered_at: prd
gate_status:
  prd_validated: true
  design_verified: true
  plan_verified: false
  evals_red: false
outcome:
  status: null
  measure_by: null
workstream: _devx/workstreams/rotation-self-heal
gate_verdicts:
  prd: PASS
  design: CONCERNS
  plan: null
  evals: null
---

## Goal

Workstream 'Rotation Self Heal' — PRD stage next. Artifacts live in `_devx/workstreams/rotation-self-heal/`.

## Status log

- 2026-07-27T10:51 — workstream scaffolded by `devx workstream new rotation-self-heal`.
- 2026-07-27T11:0x — stage PRD. Seeded from a live incident investigation
  (6-day prod outage from the 2026-07-21 credential rotation; root cause
  traced to ECS resolving `DB_PASSWORD` at task start, compounded by CI on
  `main` red since 2026-04-26 freezing prod on image `c85e350`). Ran
  `devx gate prd 462355` → FAIL (3 × expectation-threshold-not-numeric on
  E-5/E-6/E-8); rewrote those thresholds with numeric values; re-ran →
  **PASS**, flipped `prd_validated: true`, `stage: design`. Artifacts:
  `_devx/workstreams/rotation-self-heal/prd.md`, `expectations.md` (8
  E-blocks, 5 × P0). User decisions this stage: CI unblock is in scope as
  Phase 1; connect-time credential resolution (FR-5) is **in** scope
  (overrides the skill-author's recommendation to defer it).
- 2026-07-27T11:31 — stage DESIGN. Grounded in 3 parallel Explore passes
  (API db/health surfaces, terraform ECS/Secrets Manager, CI + failing
  tests). Ran `devx gate coverage 462355 --table <judged>` → **CONCERNS**
  (exit 0; 21 rows: 16 covered / 5 partial / 0 missing), flipped
  `design_verified: true`, `stage: plan`. Artifacts:
  `_devx/workstreams/rotation-self-heal/design.md`,
  `decisions/2026-07-27-design-verify.md`.
  User decisions this stage: (1) FR-6 → scheduled GitHub Action, not a
  CloudWatch alarm or an in-`ci.yml` job; (2) pre-2026-07-29 scope =
  FR-1 + FR-2 + FR-4, with FR-3/FR-5/FR-6 after; (3) the pending 90-day
  rotation cadence from `e74303f` is allowed to apply.
  **Owed before the Plan gate:** `devx revise` on the PRD — decision (3)
  contradicts the PRD non-goal "Changing the rotation cadence".
  Two design findings that changed the problem as the PRD framed it: the
  undeployed `e74303f` health probe would NOT have caught this incident
  (it probes a pooled connection, which stays authenticated across a
  rotation) and its bare `except` → 503 is a mass-task-replacement hazard
  (`health_router.py:25-27`); and the 3 Flutter failures are a date
  time-bomb (fixtures frozen at 2026-04-18 vs a 30-day `DateTime.now()`
  cutoff), not a regression — 39 test files share the fuse.
  Adversarial coverage pass caught 6 wrong file:line citations and one
  real design bug (FR-6 was reusing `deploy-services`'s family-name
  task-def lookup, which reports the newest revision rather than the
  running one — it would have masked the very freeze it exists to catch);
  all fixed before the gate. Post-judgment reconciliation, disclosed: UC-5
  moved from a net-new `bin/prod-image-age` to extending the existing
  `bin/prod-status` — table location strings updated, no status changed.
  The 5 partials (G-1..G-4, CAP-1) are all of one kind — unproven until CI
  actually runs green and until a real rotation is observed — so they are
  Plan-stage evidence work, not design gaps.
- 2026-07-27T11:40 — stage DESIGN (cont). Closed the owed PRD revision
  rather than carrying it into Plan: rewrote the "Changing the rotation
  cadence" non-goal in `prd.md` to record the 90-day decision and why
  the original bullet was unholdable (FR-4's `terraform apply` lands
  `e74303f`'s pending cadence change whether or not we choose it). Ran
  `devx revise 462355 --touched prd.md` → reset 4 flags as designed, then
  replayed the cascade: `devx gate prd 462355` → **PASS**,
  `devx gate coverage 462355 --table decisions/2026-07-27-design-coverage-table.json`
  → **CONCERNS**. Both gates back to their pre-revise verdicts;
  `design_verified: true`, `stage: plan`. Done now, at Design, because the
  cascade resets `design_verified` whenever it runs — so the cost is
  identical at Plan, but the contradiction would have been baked into
  plan.md first.
