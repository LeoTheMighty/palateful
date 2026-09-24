---
hash: stuckalarm1
type: dev
created: 2026-09-24T20:30:00-06:00
title: asgalarm1 reached ALARM correctly and cannot return to OK — the detector is deaf after its first firing
from: asgalarm1, found while waiting for the recovery transition on the night it shipped
spawned: null
status: ready
owner: null
branch: null
---

## Why this is worse than it sounds, and why it is not `edgetrig1`

`edgetrig1` says a CloudWatch alarm notifies on state *transition*, so nothing
is reported while it sits in `ALARM`. That story assumes the `ALARM` state
**ends**.

If it does not end, the two compound: **the detector is permanently deaf after
its first real firing.** Every launch-failure incident after the first is
silent, forever, with a red alarm on the dashboard that is not tracking
anything. `asgalarm1` was built to end exactly the failure of a detector that
tells nobody. It fired once, correctly, on the day it shipped — and may have
been deaf from that moment.

This is filed separately rather than folded into `edgetrig1` because it
**changes that spec's premise** rather than extending it.

## The measurement

Alarm reached `ALARM` at 18:17:51.289Z on a real burst. Last metric datapoint
19:50. At **20:22:12Z** — 32 minutes and two-plus full evaluation periods
later:

```
StateValue        ALARM
StateUpdatedTimestamp  2026-09-24T18:17:51.289Z    <- unchanged
StateReason       "[5.0 (18:02:00)]"               <- still the original firing
Period 900 · EvaluationPeriods 1 · DatapointsToAlarm 1
Statistic Sum · GreaterThanOrEqualToThreshold 1.0
TreatMissingData  notBreaching
log events since 19:51Z   0
metricTransformation      {metricName, metricNamespace, metricValue "1",
                           unit Count}   <- no defaultValue
```

Per-minute metric buckets stop dead: `19:45 → 2, 19:46 → 6, 19:47 → 4,
19:48 → 4, 19:49 → 6, 19:50 → 2`, nothing after.

## What is NOT the fix — check this before writing any Terraform

**`default_value = 0` on the metric filter cannot work here**, despite being
the established house pattern and despite the two existing alarms using it for
what looks like this exact reason. Read their own rationales:

- `alarm_fail_open.tf`: *"`default_value = 0` emits a datapoint for every log
  event the filter processes, matching or not. So data exists whenever the API
  logs at all."* Measured 288/288 buckets.
- `alarm_rds_auth.tf`: *"The export has a steady checkpoint heartbeat
  (>= 5 events every 15 min for 14 days), so the metric always has
  datapoints."*

**Both depend on their log group carrying unrelated traffic.** `defaultValue`
emits a zero per **non-matching log event** — it needs events to process. This
log group is fed *only* by the EventBridge rule for
`EC2 Instance Launch Unsuccessful`, so every delivered event matches and a
quiet period means **zero lines**, not non-matching lines. Measured: 0 events
since 19:51Z.

Applying it here yields a change that plans clean, applies clean and does
nothing — the `applygap1` failure arriving disguised as a remedy.

## The datum any explanation has to account for

The obvious mechanism is *"CloudWatch does not evaluate an alarm when the
metric publishes nothing at all"*. That is **contradicted** by this alarm's own
history:

```
17:23:51.291Z   INSUFFICIENT_DATA -> OK    <- with no data ever recorded
```

Absence drove a transition there. So a bare "missing data never recovers" is
wrong, and the real explanation must distinguish *absence from cold* from
*absence after data*.

**Two predictions were made before the event and both failed** — an
epoch-aligned model said ~20:15:51Z, a rolling-window model said ~20:06:51Z.
Neither fired. Whoever picks this up should treat published intuitions about
CloudWatch evaluation scheduling, including the two above, as unreliable here
and measure instead.

## Acceptance criteria

1. **Reproduce the stick deliberately**, on a scratch alarm with the same
   shape: sparse metric, no `defaultValue`, `notBreaching`, drive it to
   `ALARM`, stop the events, and record whether and when it recovers. Do not
   diagnose this from the production alarm's single instance.
2. **Explain the `17:23:51` counter-example** or show it is a different code
   path. An explanation that cannot account for it is not the explanation.
3. **The alarm must return to `OK` after a burst ends, demonstrated by
   driving it** — not by configuration review. Same standard as `edgetrig1`
   AC-2, for the same reason.
4. **Preserve the 385-to-1 property** (`asgalarm1`'s measured result: 385
   events, one email). A fix that restores recovery by emitting continuous
   datapoints must not turn into one-email-per-event.
5. **No second alert channel.** SNS email is the one Leo reads.

## Technical notes

- Candidate shapes, none evaluated: a CloudWatch **metric math** expression
  with `FILL(m1, 0)`, which synthesises zeros without needing log traffic;
  a scheduled heartbeat writing a `0` to the metric; or `PutMetricData` from
  the EventBridge path. The math expression is the only one that adds no
  moving parts, so cost it first.
- No Lambda exists anywhere in this Terraform. Adding one needs justifying.
- Terraform-only, so **merging is the apply** (`tfgate1`), and see
  `applygap1` — a docs-only merge landing after yours can orphan it behind a
  green run.
- Do not copy `asgalarm1`'s `period 900` forward without re-deriving it.

## Status log

- 2026-09-24 — filed by palateful-0a. Found by waiting for a recovery that
  had been predicted twice and did not arrive, on the same night the alarm
  shipped and was celebrated for firing correctly. The alarm **did** work: it
  detected a real burst, rate-limited 385 events to one email, and named the
  cause. It simply may never be able to do it again. Both halves are true and
  the first does not soften the second.
