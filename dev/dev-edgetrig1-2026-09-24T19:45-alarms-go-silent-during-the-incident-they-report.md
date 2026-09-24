---
hash: edgetrig1
type: dev
created: 2026-09-24T19:45:00-06:00
title: Every alarm we own goes silent during the incident it exists to report
from: asgalarm1, found while verifying the 2026-09-24 live burst
spawned: null
status: ready
owner: null
branch: null
---

## Why this row exists

**None of the three gaps below would be caught by a test asking "does the
alarm fire?" — because in all three cases it does.** That is the whole reason
this is worth a story. Every one of them was found by hand, by whoever had
just shipped the thing and happened to look at it while it was live; none was
found by the test suite, and none would be, however much of it there were.
The conclusion is not *more* tests of the existing kind. It is that a detector
needs to be tested for what it stays silent about, which is a different
question from whether it speaks.

## Goal

A CloudWatch alarm notifies on **state transition**, not on badness. Once it
is in `ALARM` it has already said everything it will ever say about that
incident — and about every other incident that starts before the first one
clears.

Make a second, unrelated failure audible while a first one is still open.

## The measurement this came from

On 2026-09-24 `asgalarm1` fired at 18:17:51Z on a real spot-capacity burst and
stayed in `ALARM`. Measured at 19:38Z, still in `ALARM` since that same
timestamp:

```
log group events since 18:00Z : 385
metric sum over the same span : 385   (65 / 70 / 72 / 70 / 72 / 28)
NumberOfMessagesPublished     : 1.0
NumberOfNotificationsDelivered: 1.0
```

385 events, one email, is the behaviour we wanted and the reason the alarm is
count-based. **It is also the whole problem.** Nothing in those numbers
distinguishes "385 instances of the same ongoing failure" from "384 instances
of it, plus one new failure of a completely different kind at 19:20". Both
produce exactly one email, sent at 18:17:51Z, describing the first one.

## Why this is a class and not a quirk

This is the **third** distinct instance of one shape, which is what makes it
worth a story rather than a note:

1. **`asgalarm1`'s `treat_missing_data = notBreaching`** — cannot distinguish
   "no failed launches" from "the EventBridge rule is gone". Blind to its own
   input path.
2. **`absal1`'s channel watcher** — cannot distinguish "telemetry is healthy"
   from "the watcher stopped running", and alerts through the channel it is
   watching. Blind to itself.
3. **This**: edge-triggered notification — blind to everything that happens
   while it is in the state it exists to report.

The common form: **the detector is blind during, or to, the exact condition it
was built for.** All three were found by hand, by someone who had just
shipped the thing, and none of them would be caught by any test that asks
"does the alarm fire?" — because in all three cases it does.

Cross-filed both ways with `absal1`, which holds (1) and (2). Whoever picks up
liveness should pick up all three; building the same external heartbeat three
times is the failure mode here.

## Acceptance criteria

1. **A second, distinct failure arriving during an open incident produces a
   distinguishable notification.** Not necessarily an email per event — a
   re-notify on a changed *cause*, or a periodic "still failing, now also X"
   would both satisfy this. What must not survive is total silence.
2. **Demonstrated against the real thing, not reasoned about.** Drive it: put
   the alarm into `ALARM`, then introduce a second cause while it is still
   there, and show the second one reaches the topic. A design argument that it
   should work is not an acceptance.
3. **The 385-to-1 property is preserved.** Whatever lands must not reintroduce
   one-email-per-event; that is the failure `asgalarm1` was shaped to avoid
   and it is the faster route to a muted inbox than silence is.
4. **No second alert channel.** SNS email is the one Leo reads. This is a
   constraint, not a preference.

## Technical notes

- Candidate shapes, none evaluated yet: a second alarm on a shorter period
  with `OKActions`/re-alarm behaviour; alarm-state re-evaluation via
  `EventBridge` on `CloudWatch Alarm State Change`; per-cause alarms (see
  `asgcause1`) which would at least make *different causes* separately
  audible, though not two bursts of the same cause. `asgcause1` is a partial
  mitigation and should not be mistaken for a fix.
- No Lambda exists anywhere in this Terraform. Introducing one is new
  infrastructure and needs to be justified rather than assumed.
- Terraform-only, so **merging is the apply** (`tfgate1`). Pre-register the
  plan.
- Do not copy `asgalarm1`'s `period 900` forward without re-deriving it; see
  that spec's status log for why that number is a margin nobody chose.

## Out of scope

Detection latency. Related but separate: a 900s period can only fire at a
period boundary, so `asgalarm1`'s observed 2m56s on 2026-09-24 was a
best-case draw, with expected ~8 min and worst ~16 min. That is a tuning
question about one alarm; this story is about a structural property of all of
them.

## Status log

- 2026-09-24 — filed by palateful-0a, found while independently verifying
  palateful-4f's report of the live burst. The one-email result was being read
  as rate limiting working; it is rate limiting working *and* a blind spot,
  and the same measurement shows both. Recorded before the incident closed, so
  the numbers above are from an alarm still in `ALARM` rather than
  reconstructed afterwards.
