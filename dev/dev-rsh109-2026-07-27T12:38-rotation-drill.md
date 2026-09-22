---
hash: rsh109
type: dev
created: 2026-07-27T12:38:00-06:00
title: Rotation drill, Leg A — detection backstop (FR-2 + FR-4), first proof the rule fires
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

## Split (2026-09-22, Leo's decision)

This story was one drill gated behind rsh104, rsh106, rsh107 and rsh108. The
two legs have **different prerequisites**, so bundling them meant one slow
story in the FR-5 chain blocked the whole drill — including the leg that
needs none of it. Split on Leo's decision:

- **rsh109 (this spec) — Leg A, detection backstop.** Target ~2026-10-06.
- **rsh109b — Leg B, steady state.** After the rsh105 → rsh106 → selfheal1 →
  rsh107 chain, and after this leg.

Every original acceptance criterion is kept verbatim and assigned to the leg
it measures; criteria that apply to both appear in both. Criteria **added**
at the split are marked *(added at split)*.

## Acceptance criteria — Leg A

**Gates — all must hold before the trigger:**

- [ ] **rsh104 merged and deployed**, *including the CloudTrail trail* (Leo
      approved 2026-09-22: single-region, write-only management events,
      90-day expiry). *(added at split)* The account had **no trail** —
      `describe-trails` empty, measured 2026-09-22. palateful-30's doc-based
      finding is that EventBridge receives CloudTrail detail-types only while
      a trail is logging, so without it FR-4's rule could never fire.
- [ ] **`RotationSucceeded` confirmed to reach EventBridge under the
      write-only selector** — or the rule falls back to the
      `UpdateSecretVersionStage` API call. *(added at split)* Open question
      owned by palateful-30 as of 2026-09-22.
- [ ] **logconn1 (PR #42) merged**, so `log_connections=1` is live — it is
      what makes the positive control a read-only log query. *(added at split)*
- [ ] **No parser GPU batch job running.** *(added at split)* A long batch
      holding a DB connection through the rotation could fail independently
      of api/worker and pollute attribution.

**Measurements:**

- [ ] Baseline captured: `bin/prod-status`, current 5xx rate, deployed tag +
      age, both services' `healthStatus`, and a `pg_stat_activity` snapshot.
- [ ] **Rotation-reset check.** Record `NextRotationDate` immediately before
      the trigger and again after `RotationSucceeded`; record whether the
      drill re-anchored the schedule. *(added at split)* See Technical notes.
- [ ] The roll-forward path is confirmed **before** starting — both
      force-deploy commands typed out, not in shell history. *(Leg A form of
      the original "rollback path" criterion — see Technical notes on why a
      rotation cannot be rolled back.)*
- [ ] **G-2 (Leg A)**: from CloudTrail `RotationSucceeded` to the last
      rotation-attributable 5xx is **under 5 minutes** on the detection path.
- [ ] **The rule fires — FR-4's first end-to-end proof.** `RotationSucceeded`
      → `palateful-rotation-redeploy-prod` invoked → **two** `UpdateService`
      calls (api **and** worker) → both deployments settle with **no**
      circuit-breaker rollback. *(added at split)* `aws.*` sources cannot be
      faked with `PutEvents`; rsh104 ships a direct-invoke proof of Lambda →
      ECS and explicitly leaves "the rule fires" to this leg.
- [ ] **Positive control (Leg A)**: after `RotationSucceeded`, the
      replacement tasks open connections that authenticate with the *new*
      password — proven by `connection authorized` lines in the RDS log from
      the new tasks (logconn1), **not** inferred from absence of errors.
      Observation window **≥ 3600s**. *(added at split — the original had a
      positive control for Leg B only; the `pool_recycle=3600` false-pass
      argument applies to Leg A just as hard.)*
- [ ] **G-3**: **0** manual interventions **after the rotation trigger** — any
      state-changing action following the trigger counts as an intervention
      and fails the criterion. (The trigger itself is the stimulus, not an
      intervention.)
- [ ] **G-4**: the freshness workflow's reported gap matches `git log`.
- [ ] The drill's rotation event JSON is captured and compared against the
      scheduled-rotation shape — or recorded explicitly as unverified.
      **Baseline now exists** *(added at split)*: palateful-30 measured the
      scheduled 07-28 `RotationSucceeded` — `eventType AwsServiceEvent`,
      `readOnly false`, `userIdentity.invokedBy secretsmanager.amazonaws.com`,
      `additionalEventData.SecretId` = the full secret ARN including its
      `-xVJ6GM` suffix, exactly the live `MasterUserSecret.SecretArn`.
- [ ] api reaches a steady `RUNNING` state with `HEALTHY` status. worker
      reaches steady `RUNNING`; **its `healthStatus` is expected to stay
      `UNKNOWN`** — it has no container health check until rsh107. *(Leg A
      form of the original "both services HEALTHY" criterion, which is not
      satisfiable for the worker before rsh107.)*
- [ ] `audit_errors.py --window 2h` run to catch anything unattributed.
- [ ] Every layer's engagement recorded **per leg** in
      `_devx/workstreams/rotation-self-heal/evals/E-drill-rotation.md`,
      including which layer won and which were redundant.
- [ ] Any surfaced defect filed as a `debug/debug-*.md` spec — **not** fixed in
      place.

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
- **The worker's only path to healing in Leg A is FR-4.** It has no container
  health check (`RUNNING/UNKNOWN` in prod, measured 2026-09-22), so rsh102's
  probe cannot replace it. The api self-heals through rsh102 regardless. If
  the rule does not fire, the worker stays on the dead password until someone
  force-deploys it — failing G-3 and degrading the worker for the duration.
  That is why the trail and rsh104 are hard gates, and why the Lambda's
  `ECS_SERVICES` must name **both** `palateful-api-prod` and
  `palateful-worker-prod` (it does, in palateful-30's draft).
- **A rotation cannot be rolled back — only rolled forward.** The old password
  is dead the moment the rotation completes. Recovery means getting tasks
  onto the *new* one, which works because `DB_PASSWORD` is unversioned
  `valueFrom` of the secret's `password` key (measured against task defs
  `palateful-api-prod:64` / `palateful-worker-prod:54`), so ECS resolves the
  current value at task start:

      aws ecs update-service --cluster palateful-prod --service palateful-api-prod    --force-new-deployment
      aws ecs update-service --cluster palateful-prod --service palateful-worker-prod --force-new-deployment

  Pull it if 5xx is sustained past G-2's 5-minute budget, or the api task is
  not replaced within ~10 minutes of the first 503, or anything unattributed
  appears. Any use of it fails G-3 for this leg — which is the point.
- **The drill will very likely move the natural rotation date.** [Inferred,
  strong.] `LastRotated` 2026-07-28, cadence changed 2026-07-31
  (`LastChanged`), `NextRotation` 2026-10-29 = **exactly 07-31 + 90 days** —
  so `AutomaticallyAfterDays` counts from an event and was re-anchored by the
  07-31 change. A manual `rotate-secret` almost certainly re-anchors it too:
  a drill on 2026-10-06 would push the natural rotation to ~2027-01-04. That
  is arguably the drill's real payoff — an unattended rotation on AWS's date
  becomes an attended one on ours — but it moves `devx outcome arm`'s target
  (see rsh109b). The rotation-reset criterion above turns the inference into
  a measurement at zero cost.
- **Observation inputs (provisional until rsh104 merges):** Lambda function
  `palateful-rotation-redeploy-prod`, log group
  `/aws/lambda/palateful-rotation-redeploy-prod` (palateful-30's draft).
- **Two deployments race on the api.** rsh102's probe fails the api health
  check (503 → replacement) at roughly the same moment FR-4 force-deploys it.
  Watch for circuit-breaker rollback. [Inferred] Even a rollback should be
  harmless — it returns to the same task definition, whose unversioned
  `valueFrom` still resolves the new password at start.
- **Pick a window clear of the RDS maintenance window** (Tue 07:00–08:00 UTC).
- Full context: `_devx/workstreams/rotation-self-heal/plan/agent.md` §Phase 9.

## Status log

- 2026-07-27T12:38 — emitted from plan 462355 at RED-gate PASS. Answers the
  Design stage's carry-in: G-1 and CAP-1 are proven by rsh101–rsh102; G-2, G-3
  and G-4 by this drill.
- 2026-09-22T20:00 — **split into Leg A (this spec) and Leg B (rsh109b)** on
  Leo's decision, relayed by the coordinator. Leg A's blockers narrowed from
  `rsh104, rsh106, rsh107, rsh108` to **rsh104 (with the CloudTrail trail) +
  logconn1** — rsh108 is done, and rsh106/rsh107 belong to Leg B. Target
  ~2026-10-06. Every original criterion kept verbatim and assigned to its
  leg; additions marked *(added at split)*. Three findings drive the
  additions: the account had no CloudTrail trail (palateful-30, confirmed);
  the worker's only Leg A healing path is FR-4; and the drill likely
  re-anchors the rotation schedule. Planning only — nothing touched prod.
