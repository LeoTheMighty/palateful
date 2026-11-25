---
hash: asgcause1
type: dev
created: 2026-09-24T18:40:00-06:00
title: Per-cause enrichment on the launch-failure alarm, now that $.detail.StatusMessage is confirmed present
from: asgalarm1, after the live drive on 2026-09-24 produced the real event shape
spawned: null
status: ready
owner: null
branch: null
---

## Goal

`asgalarm1` ships **one** metric filter, on `$.source`, and carries AWS's
wording for both known causes in `alarm_description` — the same static text
whichever cause fired. Split it per cause, so the alert says which one
happened instead of listing both.

## Why this was deferred, and why it is now viable

The deferral was not caution in general; it was one specific unknown.
`asgalarm1` needed a JSON path into the event, and **an EventBridge metric
filter that matches nothing is indistinguishable from an alarm that is
working** — the failure the parent spec exists to end. Shipping per-cause
filters against an unverified path risked exactly that.

The 2026-09-24 drive settled it. The real event, captured from the log group:

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

`$.detail.StatusMessage` is present and carries the cause text. `$.detail.Cause`
is also present and has **not** been inspected — read it before assuming
`StatusMessage` is the right field to match on.

## Acceptance criteria

1. **Two (or more) metric filters on `$.detail.StatusMessage`**, one per known
   cause — spot `UnfulfillableCapacity`, and the on-demand/quota case — each
   feeding its own metric.
2. **A catch-all filter stays.** The existing `$.source` filter is not
   replaced. A cause AWS words differently tomorrow must still alarm, just
   without the specific name. Removing it trades a general detector for a
   narrow one, which is a downgrade dressed as an improvement.
3. **The catch-all and the per-cause alarms must not double-notify** for the
   same burst. Measure this; do not reason about it.
4. **Each per-cause filter is proven to bite against a real recorded event** —
   replay a captured event body through `aws logs put-log-events` into a scratch
   log group, or `test-metric-filter`, and show a non-zero match. A green
   deploy of a filter you wrote is not evidence that it matches anything.
5. `alarm_description` per cause drops the other cause's text.

## Technical notes

- House pattern is `alarm_fail_open.tf` / `alarm_asg_launch_failure.tf`:
  EventBridge rule → log group → metric filter → alarm → `module.alerts.topic_arn`.
  No Lambda exists anywhere in this Terraform; do not introduce one for this.
- `alarm_description` has a hard **1024-character** AWS limit. The parent hit
  it at 776 chars carrying both messages; per-cause descriptions have room,
  but the limit fails the plan, not the apply, so it surfaces cheaply.
- Terraform-only change, so **merging is the apply** (`tfgate1`). Pre-register
  the plan before merge.
- The parent's window is `period 900`, `threshold 1`,
  `treat_missing_data notBreaching`. **Do not copy 900 forward without
  re-deriving it.** It was sized against "one failure every ~2.7 minutes", a
  24-hour average; the measured burst rate was ~13–16 seconds. It survives by
  a margin nobody chose.

## Out of scope

The `notBreaching` blind spot — this alarm cannot tell "no failed launches"
from "the EventBridge rule is gone". That is the same shape as `absal1` and is
cross-filed there; per-cause enrichment neither helps nor worsens it.

## Status log

- 2026-09-24 — filed by palateful-0a from the asgalarm1 drive report. The
  parent's status log records the measurement that unblocks this; nothing here
  is inferred from it beyond the two field names, both read from a captured
  event body rather than from documentation.
