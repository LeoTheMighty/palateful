---
hash: rsh109b
type: dev
created: 2026-09-22T20:00:00-06:00
title: Rotation drill, Leg B — steady state (all layers live, FR-5 enabled)
from: dev/dev-rsh109-2026-07-27T12:38-rotation-drill.md
status: ready
owner: null
branch: feat/dev-rsh109b
---

## Goal

Split from rsh109 on 2026-09-22 (Leo's decision). rsh109 now covers Leg A
(the detection backstop, FR-2 + FR-4). This spec is **Leg B**: the steady
state, with every layer live.

**Leg B — steady state.** `DB_PASSWORD_SECRET_ARN` **set**, so all layers are
live. FR-5 should make the rotation a complete non-event; FR-4's redeploy
fires anyway and is redundant-but-harmless; FR-2 should never trip.

*(Leg B's definition above is carried verbatim from rsh109's original Goal.)*

## Acceptance criteria

**Gates — all must hold before the trigger:**

- [ ] **rsh109 (Leg A) done** — FR-4's rule proven to fire end to end, and
      the rotation-reset behaviour measured. *(added at split)*
- [ ] **rsh106 done** — FR-5 wired (rsh105 → rsh106).
- [ ] **rsh107 done** — the worker has a container health check. Until it
      does, the "both services HEALTHY" criterion below is unsatisfiable.
      *(rsh107 in turn waits on selfheal1, which changes the probe verdicts
      it inherits.)*
- [ ] `DB_PASSWORD_SECRET_ARN` set on both services before the trigger.
- [ ] **No parser GPU batch job running.** *(added at split)*

**Measurements** — criteria carried verbatim from rsh109 unless marked:

- [ ] Baseline captured: `bin/prod-status`, current 5xx rate, deployed tag +
      age, both services' `healthStatus`, and a `pg_stat_activity` snapshot.
- [ ] **Rotation-reset check.** Record `NextRotationDate` before the trigger
      and after `RotationSucceeded`. *(added at split)*
- [ ] The rollback path is confirmed **before** starting — the exact command to
      restore `DB_PASSWORD_SECRET_ARN` and force a deployment.
- [ ] **G-2 (Leg B)**: steady-state 5xx window is ~0.
- [ ] **Positive control (Leg B)**: a connection established *after*
      `RotationSucceeded` authenticated with the *new* password, proven from
      `pg_stat_activity.backend_start` or an in-task probe — **not** inferred
      from absence of errors. Observation window **≥ 3600s**.
      *(With logconn1 live, the RDS log's `connection authorized` lines are a
      third, read-only way to prove it.)*
- [ ] **G-3**: **0** manual interventions **after the rotation trigger** — any
      state-changing action following the trigger counts as an intervention
      and fails the criterion. (The trigger itself is the stimulus, not an
      intervention.)
- [ ] Both ECS services reach a steady `RUNNING` state with `HEALTHY` status.
- [ ] `audit_errors.py --window 2h` run to catch anything unattributed.
- [ ] Every layer's engagement recorded **per leg** in
      `_devx/workstreams/rotation-self-heal/evals/E-drill-rotation.md`,
      including which layer won and which were redundant.
- [ ] Any surfaced defect filed as a `debug/debug-*.md` spec — **not** fixed in
      place.
- [ ] `devx outcome arm 462355 --measure-by <first natural rotation>` run.
      **Re-derive the date first** *(added at split)*: each drill very likely
      re-anchors `AutomaticallyAfterDays`, so "first natural rotation" is
      whatever `NextRotationDate` reads *after this leg*, not 2026-10-29.

## Technical notes

- Everything in rsh109's Technical notes applies — in particular the
  `pool_recycle=3600` false-pass warning (the positive control is
  mandatory), the manual-vs-scheduled event-shape caveat, and "a rotation
  cannot be rolled back, only rolled forward."
- **Leg B's rollback has two layers.** The FR-5 layer (unset
  `DB_PASSWORD_SECRET_ARN`, force-deploy) restores today's behaviour; the
  universal roll-forward (force-new-deployment on both services) is always
  available underneath it, because `DB_PASSWORD` is unversioned `valueFrom`.
- UC-2's unattended property is still not proven by an attended drill; it is
  scored only at the armed outcome review against a natural rotation.
- **No production code.** The only new file is the eval record.
- Full context: `_devx/workstreams/rotation-self-heal/plan/agent.md` §Phase 9.

## Status log

- 2026-09-22T20:00 — split from rsh109 on Leo's decision (relayed by the
  coordinator). Leg B's criteria moved here verbatim, including the original
  Leg B positive control and "both services HEALTHY" — which only becomes
  satisfiable after rsh107. Sequenced after Leg A so FR-4 is proven before
  it is relied on as "redundant-but-harmless." Planning only.
