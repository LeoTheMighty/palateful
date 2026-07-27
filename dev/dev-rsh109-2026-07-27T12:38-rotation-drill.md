---
hash: rsh109
type: dev
created: 2026-07-27T12:38:00-06:00
title: Rotation drill — force a rotation and measure G-2, G-3, G-4
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: ready
owner: null
branch: feat/dev-rsh109
---

## Goal

Force a rotation on purpose and measure what actually happens. Every phase
above proves a *mechanism* against mocks; this proves the *outcome* against
production. Without it, G-2 and G-3 stay inferences until ~2026-10 — and at a
90-day cadence a regression would surface late and unattended.

**Two legs, deliberately.** The layers overlap, and a single drill with
everything enabled measures only the layer that wins.

- **Leg A — detection backstop.** `DB_PASSWORD_SECRET_ARN` **unset** on both
  services, so FR-5 is inert and FR-2 + FR-4 carry the recovery. The only way
  to get a real number for the detection path, whose worst-case arithmetic
  (`design.md:101-107`) lands near 4 minutes against G-2's 5-minute budget
  "with little margin".
- **Leg B — steady state.** Variable set, all layers live. FR-5 should make
  the rotation a complete non-event; FR-4's redeploy fires anyway and is
  redundant-but-harmless; FR-2 should never trip.

## Acceptance criteria

- [ ] Baseline captured: `bin/prod-status`, current 5xx rate, deployed tag +
      age, both services' `healthStatus`, and a `pg_stat_activity` snapshot.
- [ ] The rollback path is confirmed **before** starting — the exact command to
      restore `DB_PASSWORD_SECRET_ARN` and force a deployment.
- [ ] **G-2 (Leg A)**: from CloudTrail `RotationSucceeded` to the last
      rotation-attributable 5xx is **under 5 minutes** on the detection path.
- [ ] **G-2 (Leg B)**: steady-state 5xx window is ~0.
- [ ] **Positive control (Leg B)**: a connection established *after*
      `RotationSucceeded` authenticated with the *new* password, proven from
      `pg_stat_activity.backend_start` or an in-task probe — **not** inferred
      from absence of errors. Observation window **≥ 3600s**.
- [ ] **G-3**: **0** manual interventions **after the rotation trigger** — any
      state-changing action following the trigger counts as an intervention
      and fails the criterion. (The trigger itself is the stimulus, not an
      intervention.)
- [ ] **G-4**: the freshness workflow's reported gap matches `git log`.
- [ ] The drill's rotation event JSON is captured and compared against the
      scheduled-rotation shape — or recorded explicitly as unverified.
- [ ] Both ECS services reach a steady `RUNNING` state with `HEALTHY` status.
- [ ] `audit_errors.py --window 2h` run to catch anything unattributed.
- [ ] Every layer's engagement recorded **per leg** in
      `_devx/workstreams/rotation-self-heal/evals/E-drill-rotation.md`,
      including which layer won and which were redundant.
- [ ] Any surfaced defect filed as a `debug/debug-*.md` spec — **not** fixed in
      place.
- [ ] `devx outcome arm 462355 --measure-by <first natural rotation>` run.

## Technical notes

- **This is a deliberate production action against a single-operator system.**
  Run it attended, in a window you choose, with `bin/prod-status` and
  CloudWatch open. Strictly safer than discovering a broken self-heal path at
  3am in October.
- **A short observation window produces a false pass.** Every engine sets
  `pool_recycle=3600` (`database.py:48`, `:96`, `:125`), and
  `terraform/modules/rds/main.tf:113-116` records the mechanism verbatim: the
  pool "masks the failure for hours/days while open connections stay
  authenticated, then 5xx's once the pool recycles." With FR-5 completely
  broken, a 30-minute attended watch still shows zero 5xx — the exact
  false-negative that produced the six-day outage. **The positive control is
  mandatory.**
- **The drill triggers rotation manually** (`aws secretsmanager rotate-secret`),
  which is not the scheduled path that caused the incident
  (`rotate_immediately = false`, `rds/main.tf:203`). If the two emit different
  event shapes, the drill could green-light a rule that never fires in
  October.
- **UC-2's unattended property is not proven here.** The drill proves the
  mechanism with an operator watching; UC-2/G-3 are fully scored only at the
  armed outcome review against a natural rotation.
- Rollback: the existing circuit breaker (`ecs/main.tf:366-369`, `:468-471`)
  plus the known-good fallback — `DB_PASSWORD` is still in both task
  definitions, so unsetting `DB_PASSWORD_SECRET_ARN` and forcing a deployment
  restores today's behavior.
- **No production code.** The only new file is the eval record.
- This story owns no E-id; it re-measures E-2's, E-5's and E-6's thresholds
  against production rather than against mocks. Verification type: human.
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 9.

## Status log

- 2026-07-27T12:38 — emitted from plan 462355 at RED-gate PASS. Answers the
  Design stage's carry-in: G-1 and CAP-1 are proven by rsh101–rsh102; G-2, G-3
  and G-4 by this drill.
