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

### The one unverified assumption in this spec

**That EC2 Auto Scaling actually emits `EC2 Instance Launch Unsuccessful`
to the default event bus for these failures.** I have *not* measured it. I
measured the ASG activities (`describe-scaling-activities`, 756 records),
the absence of CloudWatch metrics, and the absence of EventBridge rules —
all read from the live account. The event emission is AWS-documented
behaviour that **cannot be observed read-only**: with no rule and no
archive configured, nothing records what the default bus carries.

Stated here rather than assumed, per the entry's own rule about claims that
carry no evidence handle. **The first implementation step is to find out**,
and it is cheap: create the rule with a CloudWatch Logs target before an
SNS one, wait a few minutes — the spot ASG is failing continuously — and
read the log group.

**If the event does not arrive**, the fallbacks in order of preference:
1. An **EventBridge archive** on the default bus, to see what is actually
   published before designing against it.
2. **CloudTrail** — the `RunInstances` / fleet-level failures are API
   calls, so they are recorded whether or not an ASG event fires.
3. A scheduled Lambda polling `describe-scaling-activities` directly. Least
   elegant, but it reads the surface we *know* carries the data, because
   that is the surface this spec was written from.

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
