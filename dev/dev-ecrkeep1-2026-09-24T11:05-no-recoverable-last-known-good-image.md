---
hash: ecrkeep1
type: dev
created: 2026-09-24T11:05:00-06:00
title: Every production service has about two days of rollback history — and it cost us a diagnosis today
from: leonidbelyi-41, after ocrload1 found April's working parser image had been deleted
spawned: ocrload1
status: ready
owner: null
branch: null
---

## Goal

Keep enough image history that "deploy the version that worked" is an
available move, and that a known-good image can be compared against a
broken one.

## This is not hypothetical — it cost a diagnosis today

`ocrload1`: the parser crashes loading its OCR model. `services/parser/`
has not changed since **2026-04-16**, so the obvious experiment is to
compare the working April image against the broken one built 2026-09-23 —
which would settle in minutes whether the drift is in our resolved
`transformers` or in the published model config. **Those are different
causes with different fixes and identical symptoms.**

**The April image is gone.** So `ocrload1`'s central claim is stuck as a
labelled hypothesis, and the fix will be chosen with less information than
was available yesterday morning.

**And "redeploy what worked" — the first move in most incidents — is not
available for any service.**

## The measurement

All four repositories carry the same policy, from
`terraform/modules/ecr/main.tf:40` and `:82`:

```json
{"rulePriority":1,"description":"Keep last 10 images",
 "selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":10},
 "action":{"type":"expire"}}
```

Measured 2026-09-24:

| Repository | Images | Oldest |
|---|---|---|
| `palateful-parser` | 15 | 2026-09-22T14:17Z |
| `palateful/api` | 15 | 2026-09-22T14:09Z |
| `palateful/worker` | 16 | 2026-09-22T12:54Z |
| `palateful/migrator` | 16 | 2026-09-22T12:50Z |

**Every service's entire history begins two days ago.** Not just the
parser — the parser is merely where it was noticed.

### Why ten images is two days

`tagStatus: "any"` counts **untagged images too**, and each build pushes
more than one (the `describe-images` listing is full of untagged rows
alongside each tagged one). So ten images is roughly **three or four
deploys**, and on an active day this repository does that before lunch.
The policy reads as "keep the last ten versions"; it delivers "keep about
three."

**The parser makes this worse, not better.** It deploys on the same cadence
as everything else because `ci.yml` builds all services, but it *runs*
rarely — 24 jobs in April, none between 2026-04-22 and 2026-09-23. **So its
images age out while it is idle, and its last known-good build is deleted
without ever having been superseded by a working one.** That is exactly what
happened.

## Acceptance criteria

- [ ] **Retention expressed in time, not count.** `sinceImagePushed` with
      a day count, so the guarantee is legible ("90 days") rather than a
      side effect of deploy frequency.
- [ ] **Tagged images are retained differently from untagged.** A rule on
      `tagStatus: "tagged"` keeps release history; a separate, aggressive
      rule on `untagged` reclaims the build layers that are inflating the
      count today.
- [ ] **The parser's known-good image is protected explicitly** — it can go
      months without a successful run, so a count-based or short
      time-based rule will always delete it while idle. Consider a
      `known-good` tag applied on a verified successful import, exempted
      from expiry.
- [ ] Cost stated before the change, not after: storage is ~$0.10/GB-month,
      and GPU images are large. **Name the number so the retention is a
      decision rather than a default.**
- [ ] The policy change is verified by **listing the images afterwards**,
      not by the plan applying. Lifecycle evaluation is asynchronous — the
      parser has 15 images under a keep-10 rule right now — so a clean
      apply is not evidence about what will be kept.

## Technical notes

**This is a `pcap1`-family failure in a different costume.** The
configuration is correct, does what it says, and reports no error. Nobody
misconfigured anything; nobody ever asked *how long does "keep last 10"
actually keep*, and the answer depends on a variable (deploy frequency)
that has nothing to do with the intent.

**It was invisible until the parser needed it**, because that is the one
service whose deploy cadence and *run* cadence are wildly different. The
other three deploy and run continuously, so their two-day window has never
been tested either — it is equally thin, and equally unnoticed.

**Do not fix this by disabling expiry.** An unbounded registry is its own
problem; the ask is a retention window someone chose on purpose.

## Status log

- 2026-09-24 — filed by palateful-4f at leonidbelyi-41's direction, after
  `ocrload1` needed April's parser image and found it deleted. The policy
  is measured, identical across all four repos, and in Terraform at
  `modules/ecr/main.tf:40`/`:82`. The finding is broader than the parser:
  **every production service currently has two days of rollback history.**
