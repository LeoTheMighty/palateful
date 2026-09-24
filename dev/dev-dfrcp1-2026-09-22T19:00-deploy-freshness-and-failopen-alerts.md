---
hash: dfrcp1
type: dev
created: 2026-09-22T19:00:00-06:00
title: G3 + G11 — give deploy-freshness a recipient; alarm on rsh102 failing open
from: dev/dev-obsgap1-2026-09-22T16:00-server-side-detection-inventory.md
status: in-progress
owner: /devx-2026-09-22T1212-6355
branch: null
---

## Goal

Two working detectors with nobody listening. **deploy-freshness** has correctly
reported a 52-day-stale prod on every scheduled run since 2026-09-20 (4
verdicts) to no one. Before that, 49 runs died at `configure-aws-credentials`
and measured nothing (obsgap1 §1a). **rsh102** fails open with 200 on a broken
pool or an unreachable DB, so after it lands a total DB outage reads
`{"status":"ok"}` (G11, from 0a).

## Acceptance criteria

- [x] **G3:** deploy-freshness notifies on a red *verdict*: publish to the
      topic or add a failure-notification step. **Verified end to end
      2026-09-24** by dispatching with `synthetic-gap-days=30` — the
      workflow's own test input, not an imitation. Run `36023584634`
      concluded `failure` (correct: a red verdict exits non-zero by design),
      the `Notify on a red verdict` step published, and the email arrived.
      See `synthmark1` for the marker defect this exposed. It must distinguish a real
      verdict from the check dying at credentials, since 49 of its runs were
      the latter.
- [ ] **G11:** one metric filter on the phrase **`failing open`** in the API
      log → alarm → topic. All four fail-open branches use it
      (`db_probe.py:252, :270, :277`; `health_router.py:41`). Can only be
      wired once rsh102 is **deployed**.
      **Updated by selfheal1 (2026-09-22):** there are now **nine** emitters,
      not four — seven in `db_probe.py`, two in `health_router.py` — and the
      line numbers above are stale. Match on the phrase, never on lines. No
      existing wording changed, so a filter written against the old four
      still matches them. New ones: the passwordless-auth downgrade, the
      `NOT_CONFIGURED` classify, the missing-password classify, `probe_sync`'s
      absent-URL classify (which had no phrase at all until selfheal1 added
      it), and the router's `NOT_CONFIGURED` branch. Note also that
      `/v1/health` answers **HTTP 200 with `{"status": "degraded"}`** for
      `NOT_CONFIGURED`, so `curl -sf` passes on it and this alarm is the only
      thing that will ever report it.
- [ ] **G11 ships with a test** asserting every fail-open branch emits
      `failing open`, placed beside the filter. selfheal1 pins the behaviour
      by *driving* each path (`test_db_probe.py`,
      `test_health_credential_probe.py`) — depend on those rather than
      duplicating them, and make the new test the shape they cannot be: a
      source-level sweep that fails when emitter **#10** lands without the
      phrase. Anchor it on the verdicts (`ProbeVerdict` members and the
      functions returning them), not on log-call pattern matching. The filter makes the phrase a
      contract, and nothing else enforces it: a rewording would silently drop a
      failure mode while every verdict test still passes (0a).
- [x] **Each alert driven once and confirmed received.** Done 2026-09-24,
      after Leo subscribed and confirmed. Four paths driven, **7 messages
      published, 7 delivered, 0 failed**, all seven confirmed in his inbox
      with subjects and ALARM/OK pairing as predicted:
      `api-fail-open` (15:48:00/15:48:30), `rds-auth-failures`
      (15:50:53/15:51:19), `rds-log-export-silent` (15:53:50/15:54:16), and
      deploy-freshness as a single prose email (15:54:36).
      **The subscription check that matters** is
      `length(Subscriptions[?starts_with(SubscriptionArn,'arn:')])` — when
      first checked it returned **0** against a `length(Subscriptions)` of
      **1**, because the row was `PendingConfirmation`.
      **Caveat: driving deploy-freshness exposed a defect — its test mode
      emits an alert with no test marker that asserts a measurement it did
      not make. Filed as `synthmark1`.**

## Technical notes

- G11 is blocked by rsh102 being **deployed**, not merged.
- **Merging does not apply Terraform.** `terraform-prod` in `ci.yml` runs only
  when `deploy-images` succeeds, so a Terraform-only change merges, plans
  cleanly and is **never created**. See `dev/dev-tfgate1-…`. Whatever route is
  **Decided by Leo (2026-09-22): fix the gate** (tfgate1). **Do not merge this
  until tfgate1 is fixed and proven**, or it merges and silently never exists.
  Do not treat a merged alarm as a live one.
- Publish to `module.alerts.topic_arn` (topic `palateful-prod-alerts`, defined
  in `terraform/environments/prod/alerts.tf`). Put the alarm in **its own file**
  in `terraform/environments/prod/` so parallel alert work doesn't collide.
- **Prove it fires.** An alarm that has never been in ALARM state is a
  configured detector, not a verified one. Drive it into ALARM once (e.g.
  `aws cloudwatch set-alarm-state`) and confirm the email arrives.

## Status log
- 2026-09-22T19:00 — filed from obsgap1 (server-side detection inventory), merged ranking
  agreed with palateful-4f. Blocked-by: alrt1, tfgate1.
- 2026-09-22T12:12:19-06:00 — claimed by /devx in session /devx-2026-09-22T1212-6355
- 2026-09-22T20:55 — phase 2: spec ACs direct (v2 native); 4 ACs; workstream=none; red-artifacts=none.
- 2026-09-22T21:10 — phase 3: G3 — deploy-freshness now records a verdict
  (`fresh|stale|unknown`) and publishes red verdicts to `palateful-prod-alerts`
  before failing the job, so a credential death (49 historical runs) is
  distinguishable from a measured verdict. G11 — metric filter on `failing
  open` → alarm → topic in `terraform/environments/prod/alarm_fail_open.tf`,
  plus `libraries/utils/test/test_fail_open_phrase_sweep.py`. Coordinated the
  phrase contract with palateful-3b (selfheal1): 9 emitters after its branch,
  no rewording, so the filter covers them unchanged.
- 2026-09-22T21:30 — phase 4: single-pass adversarial review; 5 findings (2 HIGH,
  2 MED, 1 LOW); ALL fixed in-place — the load-bearing one: the SNS message was
  a literal multi-line string inside `run: |`, whose unindented continuation
  lines silently terminated the YAML block and broke the entire workflow file
  (caught by parsing the YAML, not by reading it); rebuilt with printf. Also:
  the sweep accepted a phrase logged in a nested earlier branch as cover for an
  unphrased path (false pass — tightened to block level); the metric filter
  hardcoded the log-group name (now `module.ecs.api_log_group_name`, new
  output); comment cited line numbers that move (now cites the phrase and both
  tests); ruff SIM102/SIM114/I001 in the new test. Re-review clean.
- 2026-09-22T21:40 — phase 5: sweep 5/5 green and lint-clean; mutation-verified
  twice against real sources — rewording `db_probe.py`'s unreachable branch and
  `health_router.py`'s probe-raised branch each failed the sweep at the exact
  line, and both files were restored. terraform fmt + validate pass. Workflow
  YAML parses and the step graph is as intended. utils suite: 12 pre-existing
  failures, all `ModuleNotFoundError: No module named 'alembic'` in files this
  branch does not touch (environment artifact); `utils:lint` reports 4
  pre-existing UP042/UP046 errors, also in untouched files (the known
  missing-ruff-in-venv artifact). Neither set names anything from this branch.
- 2026-09-22T21:45 — NOT met yet, and it is the AC that matters: "each alert
  driven once and confirmed received". The topic has **zero subscriptions**
  (measured: `aws sns list-subscriptions-by-topic` returns empty), so both
  alarms currently publish into a void. Filed in MANUAL.md — Leo must subscribe
  by hand before either detector can be verified end to end.
- 2026-09-22T22:10 — CI caught what my local gates missed: `tools/deploy-freshness-self-test.sh`
  runs in the `lint` job, and I never ran it. Two real defects, both mine:
  (1) `$GITHUB_OUTPUT` is unbound when the harness runs the extracted step body
  outside Actions under `set -u` — now written through an `emit` helper that
  falls back to /dev/null; (2) deeper: the harness pins THE STEP BODY's exit
  code as the verdict, and my restructure had moved the failure to a later
  step, so a stale prod exited 0. Restored the step's own `exit 1` and moved
  the notify step to `always()`, which reads outputs written before the
  failure. That is a better shape anyway: the exit code stays the check, and
  notification is additive rather than load-bearing. Self-test 9/9 green.
- 2026-09-22T22:40 — 4f's audit (via 41): a metric filter sees nothing when the
  task isn't logging, so "no fail-open lines" and "no API at all" were
  indistinguishable under `notBreaching`. Chose `treat_missing_data =
  "breaching"` over an absence companion, with `datapoints_to_alarm = 1` so a
  single fail-open line still fires immediately. Measured first rather than
  assuming the log stream is continuous: 24h of AWS/Logs IncomingLogEvents on
  `/ecs/palateful-api-prod` at 300s gives 288/288 buckets populated (~20-23
  events each), with no gap across the :64 rollout at 11:09-11:16 — so
  `breaching` does not trade a blind spot for false alarms. Rationale recorded
  in the tf file, since the same question applies to every alarm in the ranking.
- 2026-09-22T23:05 — 3b asked what happens if a SECOND replacement-driving
  verdict is added. Checked rather than assumed: my sweep fails loudly in that
  case (the new member joins FAIL_OPEN_VERDICTS and its sites are required to
  log a phrase they shouldn't), so it is noisy, not silent — but it accuses the
  wrong file. Added the inverse assertion where actionability is actually
  decided: `test_only_auth_failed_is_special_cased_by_the_router` reads
  health_router's source and requires that exactly one ProbeVerdict is compared
  against. Mutation-verified (adding a 503 branch on UNREACHABLE fails it).
  While there: rsh102's `test_only_auth_failed_is_actionable` CANNOT FAIL — it
  builds `{v for v in ProbeVerdict if v is AUTH_FAILED}` and asserts that
  equals `{AUTH_FAILED}`, true by construction for any enum. Reported to 3b;
  not fixed here (rsh102's file, and selfheal1 is mid-flight over it).
- 2026-09-22T23:45 — 41 relayed a fact that breaks part of the G3 design: Leo has
  GitHub Actions email notifications OFF, deliberately. So the Actions UI going
  red is not a channel he reads, and the 52 consecutive silent failures were
  visible the whole time to nobody. A red VERDICT already left GitHub via SNS,
  but the check's own DEATH did not — it was visible only as a red square.
  Added a second notify step on `failure() && verdict == ''`. Honest limit,
  written into the workflow: it cannot fire when the AWS credentials themselves
  failed, which is the largest historical bucket (49 of 52), because publishing
  needs those credentials. It narrows the blind spot from "any failure" to
  "credential failure"; only absal1, alerting on the absence of an expected
  heartbeat from OUTSIDE GitHub, closes the rest. This step does not make
  absal1 optional.
- 2026-09-23T00:10 — rebased onto fd732fab (selfheal1 merged). Two results worth
  separating. (1) The sweep's design claim HELD: it passes against selfheal1's
  9 emitters and the new NOT_CONFIGURED verdict with zero edits, because it
  reads fail-open verdicts from the enum rather than a list. (2) My inverse
  test was WRONG and the rebase proved it: it asserted "exactly one verdict is
  compared against" in health_router, but selfheal1 correctly singles out
  NOT_CONFIGURED for a `degraded` 200 — which is still failing open, nothing is
  replaced. My guard would have blocked a legitimate fix to protect an
  invariant I had mis-stated. Rewritten to assert what actually matters: only
  AUTH_FAILED may produce a 503, since that is what replaces the task. Two
  non-vacuity tests added beside it (a second 503 verdict is caught; a degraded
  200 is not counted). 8/8 green.
