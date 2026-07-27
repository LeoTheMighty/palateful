---
hash: 462355
type: plan
created: 2026-07-27T10:51:32-06:00
title: Rotation Self Heal
status: in-progress
stage: executing
entered_at: prd
gate_status:
  prd_validated: true
  design_verified: true
  plan_verified: true
  evals_red: true
outcome:
  status: null
  measure_by: null
workstream: _devx/workstreams/rotation-self-heal
gate_verdicts:
  prd: PASS
  design: CONCERNS
  plan: PASS
  evals: PASS
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
- 2026-07-27T12:0x — stage PLAN. Ran `devx gate coverage 462355 --table
  decisions/2026-07-27-plan-coverage-table.json` (plan mode) → **PASS**
  (8/8 covered, P0 floor met), flipped `plan_verified: true`, `stage: red`.
  Artifacts: `_devx/workstreams/rotation-self-heal/plan.md`,
  `decisions/2026-07-27-plan-critique.md`,
  `decisions/2026-07-27-plan-verify.md`.
  User decisions this stage: (1) 8 phases — FR-4 splits into a unit-testable
  Lambda handler and its Terraform/EventBridge infra, FR-5 into the utils
  provider module and the 5-engine-site + IAM wiring; (2) a 9th **rotation
  drill** phase producing measured G-2/G-3 actuals, rather than deferring
  them to a natural rotation ~2026-10 (the 90-day cadence means a regression
  would otherwise surface late and unattended).
  Critique ran (4 lenses: pm/architect/dev/qa) despite `thoroughness:
  send-it`, because the plan touches 5 surfaces ≥ `engine.critique.min_surfaces`.
  It caught two structural errors with three-lens concordance, both of which
  would have wasted a full phase each: **(a)** Phase 1's exit criterion
  ("`deploy-services` reaches success") was unreachable — an `app/`-only
  commit leaves `services_to_build` empty so every deploy job skips
  (`ci.yml:641-643`, `:703-705`, `:845-851`); E-1 now spans phases 1–2.
  **(b)** The "first `terraform apply` since 2026-04-26" — and with it the
  90-day rotation cadence — lands on **Phase 2's** push, not Phase 4's,
  because `terraform-prod` runs `-auto-approve` (`ci.yml:748`) with nothing
  consuming the plan output; the line-by-line review gate moved to Phase 2
  (T2.1). Also accepted: terraform-only phases never apply via CI and need
  `force-deploy.yml` (unmentioned before); the `archive` provider is
  declared and locked nowhere; Phase 9 had no positive control against
  `pool_recycle=3600` masking a broken FR-5; the `DB_PASSWORD` fallback
  silently re-presented a known-bad credential on the retry path; and the
  worker `CMD-SHELL` probe could crash-loop the worker because
  `libraries/utils` declares neither psycopg2 nor asyncpg.
  Coverage judge returned E-4 and E-6 **partial** on the first pass; both
  were fixed rather than argued — E-4's two unbounded connection paths
  closed by construction (single-flight cache; worker `interval = 60`), and
  E-6's second clause moved out of Phase 6's tests-after proxies into its
  named P0 artifact via T6.3b. Second pass: 8/8 covered.
  Carried into RED: the `Secret Label Updated` event shape is still
  unconfirmed (blocks E-5, P0) — Phase 4's T4.1 owns it, with the CloudTrail
  `RotationSucceeded` signal as the proven fallback.
- 2026-07-27T12:4x — stage RED. Ran `devx gate evals 462355` → **PASS**
  (6 run / 2 deferred; every runnable expectation observed RED for the right
  reason), flipped `evals_red: true`, `stage: executing`. Artifacts:
  `evals/RED-report.md`, `evals/E-7_deploy-freeze-visibility.md`,
  `evals/E-8_worker-healthcheck.md`, `services/api/tests/test_health.py`,
  `libraries/utils/test/test_rotation_redeploy_handler.py`,
  `libraries/utils/test/test_db_credential_provider.py`.
  **Config change the gate required:** E-5 and E-6 are P0 and name artifacts
  under `libraries/utils/test/`, which had no `projects:` runner — both
  resolved `command: null`, a P0 floor breach. Added a `utils` runner
  (`poetry run pytest`, cwd `libraries/utils`), verified against the existing
  suite and matching the nx `utils:test` target.
  Right-reason confirmation, run directly before the gate as well as through
  it: E-1 fails on the 30-day cutoff (fixtures frozen 2026-04-18) — pre-existing
  RED, not re-authored; E-2/E-3/E-4 on `ModuleNotFoundError:
  utils.services.db_probe` plus `test_health_check` failing the new `db` body
  field; E-5 on `ModuleNotFoundError: utils.services.rotation_redeploy` plus
  explicit module-absent AST assertions; E-6 on `ModuleNotFoundError:
  utils.services.db_credentials` plus the three source-level wiring
  assertions. `test_readiness_check` still passes in each file, so the RED is
  scoped to the missing feature rather than broken collection.
  **Three findings the authoring surfaced, all recorded rather than silently
  applied.** (1) **T6.3b's stated mechanism is impossible.** plan.md:735 has it
  "import the real `database.py`, `runner.py` and `tasks.py` … against the live
  engines"; `agent` is not installed in the `libraries/utils` venv
  (`find_spec("agent")` is `None`) and both agent modules build their engines
  *lazily* inside `_get_session_factory()`, so an import constructs nothing to
  inspect. E-6's artifact path is unchanged (no `devx revise` owed); the clause
  is proven live for `database.py`'s three sites — reloaded against a
  file-backed SQLite URL, which yields real QueuePool `Engine`s without pinning
  psycopg2 — and at the source level for the two agent sites, with the runtime
  guarantee left to T6.3's enumeration guard under the `agent` project's own
  test target. Recorded in rsh106. (2) **The api suite cannot run without
  `DATABASE_URL` in the environment.** `conftest.py:15` does
  `setdefault("DATABASE_URL", "")` and `config.Settings` rejects the empty
  string, so a bare run errors at fixture setup on a pydantic
  `ValidationError` — a wrong-reason failure. CI sets it at `ci.yml:176`/`:260`;
  the gate was run the same way. This corrects plan.md:341-347, which reads as
  though `""` is the working state (the probe's unset-URL → `OK` contract still
  stands — that is `utils.constants`, not the app settings). (3) **`services/api`
  sets `fail_under = 100`**, so *any* single-file api pytest run exits non-zero
  on coverage alone; E-2/E-3/E-4's RED verdict rests on the captured failure
  excerpt, which was independently reproduced with `--no-cov`, not on the exit
  code. (2) and (3) are recorded in rsh102.
  Emitted 9 dev specs (rsh101–rsh109) + retro (rshret) via
  `devx plan-helper emit-retro-story`; `devx plan-helper validate-emit
  rotation-self-heal` → ok. DEV.md carries the epic section with the dependency
  shape and the two Force-Deploy-only phases called out. No PLAN.md checkbox to
  flip — this workstream was created by `devx workstream new`, not from a
  PLAN.md row.
