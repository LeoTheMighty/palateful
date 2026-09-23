---
hash: azwide1
type: dev
created: 2026-09-23T13:00:00-06:00
title: Widen the GPU compute environments beyond us-east-1a/1b — buys at most a 3
from: leonidbelyi-41, relaying Leo's approval to spec it after spotback1 measured the per-AZ spot placement scores
spawned: pcap1
status: ready
owner: null
branch: null
---

## The ceiling, first

**Widening to more AZs buys at most a placement score of 3, against the 1–2
we have today.** That is the whole upside. It is not a fix.

Anyone reading "spot GPU capacity is scarce, add subnets" will assume we are
recovering the **region-level score of 6–9**. We are not, and cannot. That
number describes a request that is free to float across every AZ in the
region. **A compute environment pinned to a fixed subnet list can never make
that request.** Per-AZ, the best score available to anyone in us-east-1
today is a 3.

| Scope | Score | In our VPC? |
|---|---|---|
| Region-level, flexible across all 5 GPU types | 6–9 | — *a request we cannot make* |
| `us-east-1a` = `use1-az1` | **2** | ✅ |
| `us-east-1b` = `use1-az2` | **1** | ✅ |
| `us-east-1d` = `use1-az6` — **best in region** | **3** | ❌ |
| `us-east-1c` = `use1-az4` | 2 | ❌ |
| `us-east-1f` = `use1-az5` | 1 | ❌ |

Measured 2026-09-23 with `get-spot-placement-scores` over the spot CE's five
instance types, target capacity 1. Scores are **advisory, account-relative
and time-varying** — this session read the region figure as 6 and
palateful-0e read 9 minutes later. The per-AZ figures agreed. A 1 does not
mean "impossible"; it means the odds are poor.

All five AZs offer all five instance types (`describe-instance-type-offerings`,
5/5 each), so **this is capacity scarcity, not availability**. There is no
configuration that makes the GPUs exist.

**So the decision is: is going from 1–2 to at most 3 worth the work below?**

## Goal

Give the parser's GPU compute environments more than two availability zones
to search, so a spot request has more places to succeed — while being honest
that the ceiling is low.

## The work is larger than it looks

The VPC module makes this a **one-line change**:

```hcl
# terraform/environments/prod/main.tf:66
availability_zones = ["${var.aws_region}a", "${var.aws_region}b",
                      "${var.aws_region}d", "${var.aws_region}c"]
```

`aws_subnet.public` is `count = length(var.availability_zones)` with
`cidr_block = cidrsubnet(var.cidr_block, 8, count.index)`, and the route
table association is counted off the same list. New subnets land at
`10.1.2.0/24` and `10.1.3.0/24` — no CIDR collision, no NAT gateway needed
(they are public subnets behind the existing IGW with
`map_public_ip_on_launch = true`).

**But the measured blast radius is not one line.** Plan run against prod
state with Terraform 1.16.3 and live image tags, 2026-09-23:

```
  # module.vpc.aws_subnet.public[2]                    will be created
  # module.vpc.aws_subnet.public[3]                    will be created
  # module.vpc.aws_route_table_association.public[2]   will be created
  # module.vpc.aws_route_table_association.public[3]   will be created
  # module.batch.aws_batch_compute_environment.parser_ondemand_gpu  must be replaced
  # module.batch.aws_batch_compute_environment.parser_spot_gpu      must be replaced
  # module.batch.aws_batch_job_queue.parser            will be updated in-place
  # module.alb.aws_lb.main                             will be updated in-place
  # module.ecs.aws_ecs_service.api                     will be updated in-place
  # module.ecs.aws_ecs_service.worker                  will be updated in-place
  # module.elasticache.aws_elasticache_subnet_group.main  will be updated in-place
  # module.rds.aws_db_subnet_group.main                will be updated in-place

Plan: 6 to add, 6 to change, 2 to destroy.
```

**The AZ list is shared by the whole production network.** It is not a Batch
setting. Widening it rewires the ALB's subnets, both ECS services' task
networking, the RDS subnet group and the ElastiCache subnet group in the same
apply. Each of those reads `-> (known after apply)`, so the plan cannot show
the resulting subnet lists in advance.

### Both GPU compute environments are replaced

`subnets` **forces replacement** on `aws_batch_compute_environment`. Both CEs
go, not just spot — **both are pinned to the same two subnets**, which also
means **the pending `L-DB2E81BA` quota increase inherits this scarcity
problem**. Fixing the quota does not fix the AZs.

The module already carries `create_before_destroy` + `name_prefix`, and the
plan shows `aws_batch_job_queue.parser` updated in-place alongside — so the
queue should be rewired to the new ARNs within the same apply. **That is
precisely the deposed-ARN hazard from pcap1's corollary (f)**, and it is the
thing to verify rather than assume:

- **Record both current CE ARN suffixes before the apply.** The after-state
  alone cannot distinguish success from failure here, because a deposed CE is
  also "an on-demand CE with the right name shape".
- **After the apply, test each queue ARN as set membership against live CE
  ARNs**, so a deposed reference surfaces as unresolvable rather than as a
  plausible-looking name.

### Ordering hazard

**Append new AZs; never insert.** The subnet CIDR is `cidrsubnet(..., count.index)`,
so inserting an AZ ahead of an existing one re-indexes every subnet after it
and **destroys and recreates the live ones** — taking RDS, ElastiCache, the
ALB and ECS with them. `["a","b","d","c"]` is deliberately not alphabetical:
it puts the best-scoring new AZ (1d, score 3) at index 2 while leaving
indices 0 and 1 untouched.

## Acceptance criteria

- [ ] Pre-registered plan matches the apply exactly; anything beyond the 12
      resources above stops the apply. `terraform-prod` runs `-auto-approve`,
      so the printed plan **is** the review.
- [ ] Both current GPU CE ARN suffixes are **recorded before** the apply.
- [ ] After the apply, **every** `computeEnvironmentOrder` ARN on
      `palateful-parser-queue-prod` resolves against a live
      `describe-compute-environments` result — not merely "looks like an
      on-demand CE".
- [ ] Both new CEs reach `VALID` / `ENABLED` and list **four** subnets.
- [ ] `/v1/health` stays green across the apply, and the ALB reports healthy
      targets throughout. The ALB, ECS, RDS and ElastiCache changes are the
      part of this change that can take production down; Batch is not.
- [ ] A test import runs end-to-end afterwards. **Not** an acceptance
      criterion that it lands in a new AZ — that is luck, not correctness.
- [ ] Re-measure `get-spot-placement-scores` after the change and record the
      four-AZ figure. If it has not moved off 1–3, say so plainly rather than
      declaring the work successful because it applied cleanly.

## Technical notes

**Do not judge this by whether the next import starts.** Spot placement is
probabilistic; one success proves nothing and one failure disproves nothing.
The honest measure is the re-measured score, and the honest expectation is
that it lands around 3.

**Cheaper alternatives worth weighing first, since the ceiling is 3:**

1. **Wait for `L-DB2E81BA`.** Leo has the increase filed. On-demand has no
   placement-score problem — it either has capacity or the quota blocks it.
   At ~$7.50/month for April's real volume (40 jobs, 8.20 GPU-hours; see
   pcap1's costing correction) this is the cheapest path to *reliable*, and
   it needs no infrastructure change at all.
2. **Widen the instance type list further.** The spot CE already carries five
   types; more types is a Batch-only change with no network blast radius.
3. **Do nothing and accept queueing**, with the watcher fixed so a queued job
   is not silently marked failed after 90 minutes (`prcon1`).

**This spec exists because the scarcity is real, not because widening is
recommended.** Option 1 is the better answer to the same problem, and this
work only becomes attractive if the quota increase is refused.

## Status log

- 2026-09-23 — filed by palateful-4f at Leo's request, relayed via
  leonidbelyi-41, after `spotback1` measured the per-AZ placement scores
  while reverting the queue to spot-first. Headline is the **ceiling of 3**,
  per Leo's instruction that the spec must not read as "recover the 6/9".
  Blast radius measured with a real plan against prod state under Terraform
  1.16.3, not estimated: **6 add, 6 change, 2 destroy**, touching RDS,
  ElastiCache, the ALB and both ECS services. Awaiting Leo's decision.
