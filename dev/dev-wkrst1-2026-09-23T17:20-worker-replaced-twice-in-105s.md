---
hash: wkrst1
type: debug
created: 2026-09-23T17:20:00-06:00
title: prod worker replaced twice in 105 seconds — trigger unidentified
from: dev/dev-prcon1-2026-09-23T02:30-reconcile-batch-state-to-parser-rows.md
status: ready
owner: null
branch: null
---

## Goal

On 2026-09-22 the prod worker service replaced its task **twice in 105
seconds**. Nobody has looked at why. It surfaced only because it destroyed an
in-flight 90-minute Celery vigil (`prcon1`), and it would otherwise have been
invisible.

## Measured

`aws ecs describe-services --cluster palateful-prod --services palateful-worker-prod`:

```
20:05:58  has stopped 1 running tasks: (task 733963f4b7894998b6935571b407b143)
20:05:59  has started 1 tasks:         (task c38fa30aa92349b98923fc2602bcd87a)
20:07:43  has stopped 1 running tasks: (task c38fa30aa92349b98923fc2602bcd87a)
20:07:44  has started 1 tasks:         (task 7ce792823a404533a801f3db9c489293)
20:11:30  (deployment ecs-svc/5381258920964928019) deployment completed
20:11:30  has reached a steady state
```

**The trigger is unidentified.** Stating that rather than naming a fourth
plausible cause: three separate attributions to a specific deploy were made
during the investigation and **all three were withdrawn**. The nearest CI run
(`fd732fab`) did not touch ECS until **20:17:15** (`terraform-prod`) and
**20:19:22** (`deploy-services`) — **eleven minutes after** the first
replacement.

**Why it reads as a failure rather than a rollout:** a task stopped, replaced,
then stopped again 105 seconds later and replaced, before reaching steady
state. A normal rollout replaces once.

## Acceptance criteria

- [ ] Establish why those tasks stopped — exit codes / stopped reasons for
      `733963f4…` and `c38fa30a…` (ECS retains stopped-task detail only
      briefly, so **check whether it is still available before planning
      around it**; if it has aged out, say so and instrument for next time).
- [ ] Determine whether this is recurring: how often has
      `palateful-worker-prod` replaced tasks outside a deploy?
- [ ] If tasks are exiting non-zero, that is a live worker defect and gets its
      own fix.
- [ ] Whatever the cause, **worker replacement must be visible** — it
      currently isn't, and it silently destroyed user work.

## Technical notes

- Found via `prcon1`; the row exists because the event mattered, not because
  the cause is known.
- Related: `alrt1`/`absal1` — nothing alerts on worker churn today.
- Do **not** assume a deploy. That assumption has already been wrong three
  times on this exact event.

## Status log
- 2026-09-23T17:20 — filed at palateful-41's request while chasing prcon1's
  discriminator. Events recorded as measured; trigger deliberately left open.
