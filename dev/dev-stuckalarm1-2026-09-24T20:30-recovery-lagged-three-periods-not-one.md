---
hash: stuckalarm1
type: dev
created: 2026-09-24T20:30:00-06:00
title: asgalarm1 took 46 minutes to recover from a 15-minute window — the blind spot is bounded, but by 3x what the config implies
from: asgalarm1, found by waiting for a recovery transition that was predicted twice and arrived late
spawned: null
status: ready
owner: null
branch: null
---

> **This spec was first filed as "the alarm cannot return to OK". That was
> wrong — it recovered at 20:36:51.290Z, fourteen minutes after filing.** The
> original framing would have sent someone chasing a broken recovery path
> that works. What survives is narrower and still real: the recovery took
> **46 minutes and 20 seconds** for an alarm whose period is 15 minutes. See
> the status log for the full correction.

## Goal

`asgalarm1` is `period 900`, `1` evaluation period, `notBreaching`. A reader
of that config — including both sessions who predicted it on the night —
expects recovery roughly one period after the last failure. It took **just
over three periods**.

Find out why, and either fix it or write the real number where the config is
read, so nobody sizes anything against 15 minutes again.

## The measurement

```
19:50:31.109Z   last launch-failure datapoint
20:36:51.290Z   ALARM -> OK        <- 46m20s later
  StateReason: "Threshold Crossed: no datapoints were received for 1 period
                and 1 missing datapoint was treated as [NonBreaching]."
```

Full transition history:

```
17:23:51.291Z   INSUFFICIENT_DATA -> OK      (no data had ever been recorded)
18:17:51.289Z   OK -> ALARM
20:36:51.290Z   ALARM -> OK
```

**Three transitions, all at `:51.29x` past the minute.** That is a fixed
evaluation offset, and it is the only part of anybody's model that survived
the night.

## Why 46 minutes is the question, not 15

The reason string says `notBreaching` fired on **one** missing period. So the
mechanism is not "missing data never recovers" — the feature worked exactly
as documented. **The open question is why that single missing period took
~46 minutes to be evaluated**, when one 900s period after 19:50:31 closes
around 20:06.

Candidate: CloudWatch looks back beyond the evaluation range for real
datapoints to fill missing slots, so the 19:50 datapoint kept satisfying the
window until it aged out. **Not verified. Do not build on it.**

**Treat every published intuition about CloudWatch evaluation scheduling as
unreliable here, including the ones in this repo.** Three predictions were
made before the event by two sessions — ~20:06:51Z (rolling window),
~20:15:51Z (epoch-aligned), and an earlier 19:58–20:05Z — and **all three
were wrong**. Measure.

## What this does to `edgetrig1`

`edgetrig1` says a second, unrelated failure arriving while the alarm is in
`ALARM` produces no notification. That gap is real and unchanged. What this
story supplies is its **size**: the blind window is **bounded by the
recovery**, and the measured recovery is ~46 minutes, not the ~15 the config
suggests.

Bounded at 46 minutes is much less alarming than the "permanently deaf"
reading this spec was first filed under — and still three times worse than
anyone reading `period 900` would assume.

## What is NOT the fix — check before writing Terraform

**`default_value = 0` on the metric filter cannot work here**, despite being
the house pattern. Both existing uses say so in their own comments:

- `alarm_fail_open.tf`: *"emits a datapoint for every log event the filter
  processes, matching or not. So data exists whenever the API logs at all."*
  Measured 288/288 buckets.
- `alarm_rds_auth.tf`: *"The export has a steady checkpoint heartbeat."*

Both depend on the log group carrying **unrelated traffic**; `defaultValue`
emits a zero per *non-matching log event*. This log group is fed only by its
own EventBridge rule, so a quiet period is **zero lines**, not non-matching
lines (measured: 0 events between 19:51Z and the recovery). It would plan
clean, apply clean and do nothing — `applygap1`'s failure arriving as a
remedy.

Tonight's recovery reinforces this rather than weakening it: the `OK` came
from `notBreaching`, **not** from a datapoint existing.

## Acceptance criteria

1. **Reproduce the lag on a scratch alarm** of the same shape — sparse
   metric, no `defaultValue`, `notBreaching` — and measure last-datapoint to
   `OK` across at least three runs. One production instance is an anecdote.
2. **Explain the ~3x, or bound it.** If the lookback hypothesis holds, derive
   the worst case rather than observing one sample.
3. **Write the measured recovery time next to the `period` in the Terraform**,
   whatever the outcome. The config reads as 15 minutes and behaves as 46;
   that gap is the defect even if nothing else changes.
4. **Do not "fix" it by shortening the period** without re-deriving the
   detection side — `asgalarm1`'s 900s window is already a margin nobody
   chose (see its status log), and the same number governs both directions.
5. Preserve the 385-to-1 property; no second alert channel.

## Status log

- 2026-09-24T20:30 — filed by palateful-0a as **"the alarm cannot return to
  OK"**, from a measurement at 20:22:12Z: `ALARM` unchanged 32 minutes and
  two-plus periods after the last datapoint.

- 2026-09-24T20:37 — **that premise was wrong and the spec is rewritten.** The
  alarm recovered at 20:36:51.290Z, fourteen minutes after I filed. The
  measurement was accurate; the conclusion drawn from it was not, and it was
  drawn from **a single observation of a process I had already mispredicted
  twice that hour**. Having both models fail should have been evidence that I
  could not yet tell "late" from "never" — instead I read it as evidence of a
  defect, which is the more alarming of the two available stories and the one
  I had least support for.

  What that nearly cost: the original version told a reader the detector was
  *permanently deaf after its first firing* and gave `edgetrig1` an unbounded
  amplification. Someone would have gone looking for a broken recovery path
  that works fine.

  The narrower finding survives and is worth the story on its own: **46m20s
  to recover a 15-minute window.** Kept, with the false version above it
  rather than deleted, because a spec that quietly changes its own premise
  teaches nothing about how the premise was reached.

- 2026-09-24T20:45 — **the generalisable form, which is about calibration
  rather than CloudWatch.** I had two failed predictions of this same process
  within the hour. I treated them as background — embarrassing, already
  corrected, not bearing on the next question. They were the opposite:
  **prior failures to predict a process are evidence about your own
  resolution, not noise to set aside.** Two misses inside an hour said,
  quantitatively, that I could not yet tell *late* from *never* on this
  system. That should have widened the interval I was willing to call
  normal. Instead it dropped out of the reckoning entirely, and what filled
  the gap was the more alarming of two available stories — the one with less
  support behind it.

  The asymmetry is the dangerous part. A miscalibrated interval does not
  produce random errors; it produces **confident ones in the direction of
  whichever story is easier to tell**, and "the thing is broken" is always
  easier to tell than "I don't yet know how long this takes". So the check
  is not "am I sure?" but **"how many times have I been wrong about this
  exact process today, and have I widened anything as a result?"**

  Worth noting the one prediction that held: the cause discriminator for the
  `OK` (spot desired 4 → 0 before `order1` flips = the cancel, not the flip)
  resolved exactly as pre-registered. The difference is that it was a
  prediction about **which of several causes**, decided by an observation
  chosen in advance — not a prediction about **when**, against a process
  whose timing I had already demonstrated I could not model. Pre-registration
  worked; the timing estimates that failed were never pre-registered as
  falsifiable, they were stated as expectations.
