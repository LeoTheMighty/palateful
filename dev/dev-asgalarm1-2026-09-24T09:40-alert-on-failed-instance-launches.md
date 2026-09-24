---
hash: asgalarm1
type: dev
created: 2026-09-24T09:40:00-06:00
title: Alert on failed instance launches — AWS already writes the diagnosis, nobody reads it
from: leonidbelyi-41, relaying Leo, after spotback1 found 756 failed launch activities carrying both incidents' root causes verbatim
spawned: pcap1
status: ready
owner: null
branch: null
---

## What makes this different from everything else in the ranking

**The signal already exists, is already durable, and is already correct.**
Nobody has to build detection. AWS has been writing the diagnosis of both
production incidents, in plain English, at the moment each occurred, into a
surface no one has ever read.

**Spot, 2026-09-24T15:32:40Z** — written while a user's import sat queued:

> `Could not launch Spot Instances. UnfulfillableCapacity - Unable to
> fulfill capacity due to your request configuration. Launching EC2
> instance failed.`

**On-demand, 2026-09-23T18:53:59Z:**

> `Could not launch On-Demand Instances. VcpuLimitExceeded - You have
> requested more vCPU capacity than your current vCPU limit of 0 allows for
> the instance bucket that the specified instance type belongs to.`

These **name the cause**. They do not imply it or require correlation. The
second one says *"your current vCPU limit of 0"* — the finding that took two
sessions and several hours to reach by inference from quota tables.

**Volume, measured 2026-09-24:**

| Auto Scaling Group | Failed activities | Since |
|---|---|---|
| `…parser-spot-gpu-prod-…` | **540** | 2026-09-23T15:10Z |
| `…parser-ondemand-gpu-prod-…` | **216** | 2026-09-23 |
| **Total** | **756** | — |

**756 recorded failures. Zero alerts. Zero reads.**

### Why no existing detector could have caught either

**The job never failed.** It stayed `RUNNABLE` and the Batch job status was
correct throughout. Nothing in the pipeline was in an error state: the
queue was healthy, both compute environments read `VALID`/`ENABLED`, and
`desiredvCpus` was a perfectly ordinary 4. **The failure lived one layer
below everything anyone was watching**, in the ASG that Batch manages on
our behalf and that no dashboard, alarm or script in this repo mentions.

This is also why it survived two independent verifications of the compute
environments — see pcap1's *"verified the shape, never the capability"*.

## Goal

When an instance launch fails, a human learns within minutes, with AWS's own
message in the alert.

## Design

**EventBridge, not CloudWatch metrics.** Measured 2026-09-24: the ASGs have
**no** CloudWatch metrics published and `EnabledMetrics` is `[]`, and Batch
creates these ASGs so we do not own their configuration. But EC2 Auto
Scaling emits **`EC2 Instance Launch Unsuccessful`** to the default event
bus, and the account currently has **zero EventBridge rules** — so this is
greenfield rather than a modification.

```
EventBridge rule
  source       = ["aws.autoscaling"]
  detail-type  = ["EC2 Instance Launch Unsuccessful"]
  → target: module.alerts.topic_arn
```

The event detail carries `StatusMessage` — the verbatim text above — so the
alert names the cause without a lookup.

**Deliberately not scoped to the parser ASGs.** Any failed launch in this
account is worth knowing about, and scoping to names that Batch generates
(`…-asg-986a0e04-…`) would break on the next compute-environment
replacement, which `pcap1` has already done twice.

### Rate limiting is required, not optional

540 failures in 24 hours is **one every ~2.7 minutes**, and they arrive in
bursts of two or three per attempt. A rule that pages on every event is a
rule someone mutes in an hour — which is (b) by another route: a detector
whose output reaches a human who has stopped listening.

Either an SNS-side throttle, or a small Lambda/metric-filter that converts
events to a **count** and alarms on *"failed launches > 0 over 15 minutes"*.
Prefer the count: it fires once per incident rather than once per attempt,
and its recovery is meaningful.

## The blocker that makes this honest

**`palateful-prod-alerts` has zero confirmed subscriptions.** Measured
2026-09-22 and unchanged: the three existing alarms publish into a void.
**Shipping this rule without a subscriber produces a fourth detector that
tells nobody** — corollary (b) of the consolidated LESSONS entry, committed
by the spec that cites it.

`MANUAL.md` already carries `dfrcp1` — *subscribe to
`palateful-prod-alerts`* — and it blocks two detectors today. **This makes
three. This spec is not done until a confirmed subscription exists**, and
`length(Subscriptions[?starts_with(SubscriptionArn,'arn:')])` is the check,
because a `PendingConfirmation` subscription appears in the console and
delivers nothing.

## Acceptance criteria

- [ ] EventBridge rule exists, targets `module.alerts.topic_arn`, in
      terraform — not click-ops.
- [ ] **Driven into the failure state and observed.** Not "configured".
      Uniquely for this spec, **the failure is happening right now** — the
      spot ASG is failing every few minutes — so the rule can be verified
      against a live, ongoing, real failure the moment it is applied.
      There is no excuse here for shipping an unexercised detector.
- [ ] The alert body contains the verbatim `StatusMessage`. An alert that
      says "a launch failed" without saying `VcpuLimitExceeded … limit of 0`
      throws away the entire value of this signal.
- [ ] Rate limiting demonstrated against the current burst: confirm the
      chosen mechanism emits **once per incident**, not 540 times.
- [ ] **A confirmed (not `PendingConfirmation`) subscription exists on
      `palateful-prod-alerts`** before this is called done.
- [ ] Retroactive check: the rule would have fired on 2026-09-23T18:53:59Z
      and on 2026-09-24T15:32:40Z. State which, and why.

## Technical notes

**Cost:** negligible. EventBridge charges nothing for AWS-source events on
the default bus; SNS email is effectively free at this volume once rate
limiting is in place.

**This is the cheapest item in the detection ranking by a wide margin**, and
it is cheaper than anything in `clidet1`, because the collection problem is
already solved by AWS. Every other gap in that ranking requires instrumenting
something. This one requires subscribing to something.

**The `azwide1` connection.** `UnfulfillableCapacity - Unable to fulfill
capacity due to your request configuration` is **AWS pointing at the
request configuration** — five instance types across two AZs. That is
evidence for widening rather than a placement-score inference. It does not
change `azwide1`'s ceiling of 3 or its blast radius, and Leo's decision
still waits on `L-DB2E81BA`; but the argument there is now AWS's rather
than ours.

## Status log

- 2026-09-24 — filed by palateful-4f at Leo's direction via
  leonidbelyi-41, jumping the filing halt. Found while watching a live
  import stall: `describe-scaling-activities` on the Batch-managed ASGs
  carries both incidents' root causes verbatim, 756 failures deep, unread.
  The same lookup also corrected an earlier claim of mine that the
  on-demand environment "produced zero instance requests" — it produced
  216 failed ones; I had queried `describe-fleets` and
  `describe-spot-instance-requests`, which correctly return nothing because
  Batch uses neither.
- 2026-09-24 — implemented by palateful-0a. All four of the spec's measured
  claims re-verified first, not assumed: 3 ASGs all report **0** enabled
  metrics (my first query filtered on `Batch` in the name and matched
  nothing — an empty result, not an empty metrics list; re-run unfiltered);
  the account has **0** EventBridge rules; `palateful-prod-alerts` now has
  **1 confirmed, 0 pending** subscriptions, so the spec's own blocker is
  cleared; and spot is still failing live (16:28:23Z and 16:27:22Z today).

  **Design deviation, and why.** The spec prefers a count-based alarm for
  rate limiting, but AC-3 requires the verbatim `StatusMessage` in the alert
  body — and a CloudWatch alarm notification cannot carry the triggering log
  line. Those two ACs cannot both be satisfied by one alarm. Resolved without
  a Lambda (there is no Lambda anywhere in this Terraform, so one would be
  new infrastructure) by using the house pattern from `alarm_fail_open.tf`:
  EventBridge → log group → metric filter → alarm, with **AWS's own wording
  for both known causes carried in `alarm_description`**, which *is* included
  in the SNS payload. The live event's exact text stays authoritative in the
  log group, and the description says so.

  **One filter on `$.source`, not per-cause filters on
  `$.detail.StatusMessage`.** That JSON path is the one thing here that
  cannot be verified before a real event lands, and if it were wrong every
  per-cause filter would match nothing — a detector that alerts on nothing,
  which is the failure this spec exists to end. Per-cause enrichment is a
  follow-up once a live event confirms the shape; the live drive will
  produce that shape within minutes of apply.

  `alarm_description` hit AWS's 1024-character limit on the first plan and
  was trimmed to 776, keeping both verbatim messages.
- 2026-09-24 — **the `notBreaching` limitation is the same unresolved shape
  as absal1's, and whoever solves liveness should solve both.** This alarm
  cannot distinguish "no failed launches" from "the EventBridge rule is
  gone"; absal1 cannot distinguish "telemetry is healthy" from "the watcher
  stopped running", and its own channel-watcher alerts through the channel
  it watches. In all three cases the detector is blind to its own input
  path, and no threshold, default or `treat_missing_data` setting reaches
  it — the check would have to come from outside the thing being checked.
  They are one problem wearing three costumes, and fixing them separately
  would mean building the same external heartbeat three times. Cross-filed
  so the next person to pick up liveness finds both ends of it.
- 2026-09-24 — **applied, then exercised by a real burst. All four checks
  passed; nothing was manufactured.**

  **Apply.** `#87` merged as `41e7a8f8`; `terraform-prod` job log reads
  `Apply complete! Resources: 6 added, 0 changed, 0 destroyed.` at
  17:22:29Z — matching the pre-registered plan exactly, and read from the
  job log rather than inferred from the merge. All six resources were then
  verified individually. The alarm settled `INSUFFICIENT_DATA` → `OK` at
  17:23:51 with CloudWatch stating *"1 missing datapoint was treated as
  [NonBreaching]"*, which is the `treat_missing_data` setting confirming
  itself rather than being read back off the config.

  **Drive.** Leo's retry queued at 18:14:55Z and spot failed as it has been
  failing. Four independent checks, each of which could have failed alone:

  1. The log group received **38 events** against ~35 visible `Failed`
     scaling activities — the rule matches a real
     `EC2 Instance Launch Unsuccessful`. This was the only genuinely
     unverified element before the drive.
  2. The metric filter recorded datapoints — the alarm reason cites `5.0`
     in the 18:02 period.
  3. The alarm transitioned `OK` → `ALARM` at 18:17:51Z: *"Threshold
     Crossed: 1 out of the last 1 datapoints [5.0] was greater than or
     equal to the threshold (1.0)"*.
  4. **One email, not 38**: `NumberOfMessagesPublished 1.0`,
     `NumberOfNotificationsDelivered 1.0`. The count-based design did the
     thing it was chosen for.

  **The event shape, now measured, resolving the deferred question above:**

  ```
  source     : aws.autoscaling
  detail-type: EC2 Instance Launch Unsuccessful
  detail keys: Origin, Destination, Action, Description, EndTime, RequestId,
               ActivityId, StartTime, EC2InstanceId, StatusCode,
               StatusMessage, Details, Cause, AutoScalingGroupName
  StatusMessage: "Could not launch Spot Instances. UnfulfillableCapacity -
                  Unable to fulfill capacity due to your request
                  configuration…"
  ```

  `$.detail.StatusMessage` is present, so per-cause enrichment is now a
  viable follow-up — explicitly a follow-up, not a change to what shipped.

  **This proves nothing about `ocrload1`.** The GPU job was still `RUNNABLE`
  throughout. The alarm firing means the detector works, not that the
  capacity problem moved.

  **Window calibration — the margin here is luck, not design.** The
  15-minute period was sized against this spec's own "one failure every
  ~2.7 minutes". The real rate in the drive was one every **~13–16
  seconds** — roughly an order of magnitude faster. The window survives
  because a count-over-15-minutes alarm degrades gracefully as the rate
  rises (more events, same one alert), not because anyone picked 900s with
  this rate in mind. Recording it so the next person sizing a window off
  the 2.7-minute figure knows that figure is a 24-hour average across idle
  stretches, not a burst rate.

  **Near-miss worth keeping.** The first `EnabledMetrics` check in the
  entry above returned `[]` because my filter on `Batch` in the ASG name
  matched nothing — an *empty query*, not an empty metrics list. It would
  have confirmed 4f's claim by accident. An independent check that lands
  on the same answer by accident is indistinguishable from a real
  corroboration, and the only thing that separated them was re-running it
  unfiltered.
- 2026-09-24 — **the pipeline is measurably lossless, and the same number
  exposes a blind spot.** At 19:38Z, with the alarm still in `ALARM` since
  18:17:51.289Z, the log group held **385** events since 18:00Z and the metric
  summed to **exactly 385** over the same span (65 / 70 / 72 / 70 / 72 / 28 in
  the 900s buckets from 18:15). Filter and metric agreeing to the event is
  stronger evidence that no events are being dropped between EventBridge, the
  log group and the metric filter than either figure is on its own — a count
  that merely looks plausible proves nothing about the stage before it.

  `NumberOfMessagesPublished` and `NumberOfNotificationsDelivered` both stayed
  at **1.0** across all 385. That is the count-based design working. It is
  also why **a second, unrelated failure during this window would have been
  silent** — a CloudWatch alarm notifies on state transition, so everything
  after the first one is unreported. Filed as `edgetrig1`; it is the third
  instance of the same shape as this alarm's `notBreaching` limitation and
  `absal1`'s channel watcher.

  **Correction to a figure already in circulation:** the 2m56s from job
  submission (18:14:55Z) to alarm (18:17:51Z) is arithmetically right but is
  **not this alarm's detection latency**. A 900s period can only fire when a
  period closes; the burst began ~18:15 against a boundary at 18:17:00, plus
  ~51s of CloudWatch evaluation delay. Starting just *after* a boundary would
  have taken **~15m50s** for the identical burst. Expected ~8 minutes, worst
  ~16. Recorded because "under three minutes" had already been reported to
  Leo, and because it is the same error as the window calibration above — a
  margin nobody chose, restated as a property.
