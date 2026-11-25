---
hash: goodtag1
type: dev
created: 2026-09-24T11:40:00-06:00
title: Tag the image that actually worked — and never the one that merely started
from: leonidbelyi-41, after ecrkeep1 shipped the socket but not the plug
spawned: ecrkeep1
status: ready
owner: null
branch: null
---

## Goal

When a real import completes, tag the image that did it `known-good-<sha>`,
so `ecrkeep1`'s rule 2 has something to protect.

**`ecrkeep1` rule 2 is inert until this exists.** It keeps the last 3
`known-good-*` images regardless of age — and today there are none. Rules 1
and 3 deliver the retention improvement on their own; **this is the part
that would actually have saved April's parser image.**

## The signal, and why the obvious one is wrong

**Use `parser_batches.status = 'succeeded'`.**

**The tempting signal is "a run happened", and it would have tagged a broken
image tonight.** Worked counter-example, 2026-09-24:

- Batch job `272aae30` waited 65 minutes, got a `g4dn.xlarge` spot instance,
  and reached `STARTING` then `RUNNING`.
- **The container exited 1 after 32 seconds**, crashing on model load
  (`ocrload1`).
- Anything keyed on the job starting, the instance launching, the task
  reaching `RUNNING`, or the deploy succeeding **would have tagged that
  image `known-good`** — and `ecrkeep1` would then have protected the one
  image we most want deleted, for as long as the rule holds it.

`parser_batches.status` cannot be satisfied that way. It is written by the
completion callback in `parser_batch_completion.py`, only on a terminal
state, and it carried the true reason tonight — *"Essential container in
task exited"*, not a timeout. **Verified working the same day, under a real
failure**, which is a stronger basis than any of the alternatives.

## Acceptance criteria

- [ ] On a `parser_batches` row reaching **`succeeded`**, tag the image that
      ran it `known-good-<git-sha>` in ECR.
- [ ] **The tag names the image that actually ran**, resolved from the Batch
      job's job definition → `containerProperties.image`, **not** from the
      current `main` or the newest ECR push. By the time a slow batch
      finishes, those can differ — and tagging the wrong image is worse than
      tagging nothing, because rule 2 will then protect it for months.
- [ ] **Idempotent.** Re-tagging an already-tagged image is a no-op, not a
      second tag and not an error.
- [ ] **Failure to tag must not fail the import.** This is bookkeeping; a
      user's completed import must not be reported as failed because ECR was
      unreachable. It must, however, be **visible** — a silent failure here
      is `dfrcp1`'s whole subject, and the result is an empty protection set
      that reads as "nothing has succeeded yet".
- [ ] **Driven once, end to end**, against a real completed import. Not a
      synthetic row. `ecrkeep1`'s rule 2 is unexercised until a
      `known-good-*` image exists and survives an eviction cycle.
- [ ] Verified by **listing ECR images afterwards**, not by the tagging step
      exiting 0 — the same async caveat as `ecrkeep1`.

## Failure modes to design against

**The tagger is the thing that might be wrong.** `ecrkeep1` bounds this at
three images for exactly that reason — accumulate rather than
replace-on-write, so one bad tagging event cannot destroy the last good
image. That mitigation assumes bugs here; do not treat it as slack.

1. **Tagging a broken image** — the case above. Mitigated by the signal, not
   by care.
2. **Tagging the wrong image** — resolving the tag from `main` rather than
   from the job that ran. Mitigated by reading the job definition.
3. **Never tagging at all** — the protection set stays empty and looks
   identical to "no import has succeeded yet". **Assert non-zero:** after
   the first successful import there must be ≥1 `known-good-*` image, and
   something should say so rather than leaving the absence to be noticed
   months later by someone who needs a rollback.
4. **Tagging so often the bound evicts good images** — if every success
   tags, three successes cycle the window. Consider tagging only when the
   image differs from the newest `known-good-*`.

## Technical notes

**Where this runs is open.** The completion callback is the natural place
(it already knows the batch and the outcome), but it runs in the API/worker
task, which would need ECR tagging permission it does not have today. A
scheduled reconciler — *"for the newest succeeded batch, ensure its image is
tagged"* — is slower, needs no new permission on the hot path, and is
idempotent by construction. **Prefer the reconciler**; it also self-heals
failure mode 3.

**Cost is one ECR `put-image` call per success**, and at April's volume that
is a handful per month.

## Status log

- 2026-09-24 — filed by palateful-4f at leonidbelyi-41's direction, after
  `ecrkeep1` shipped rule 2 as a socket with nothing to plug into it. The
  signal choice is the substance: tonight's 34-second exit is a live
  counter-example to every "a run happened" signal, and it is the reason
  `parser_batches.status = 'succeeded'` is the one to use.
