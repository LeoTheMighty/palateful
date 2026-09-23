---
hash: bvcpu1
type: dev
created: 2026-09-23T00:30:00-06:00
title: Every Terraform apply proposes resetting Batch desired_vcpus to 0
from: dev/dev-tfgate1-2026-09-22T19:00-terraform-only-changes-never-apply.md
status: done
owner: palateful-0e
branch: feat/dev-bvcpu1
---

## Goal

`module.batch.aws_batch_compute_environment.parser_spot_gpu` declares
`desired_vcpus = 0` ("Start at zero") with **no `ignore_changes`**. AWS Batch
owns that value at runtime: it scales the compute environment up to run queued
jobs and back down to `min_vcpus` when idle. So whenever Batch has scaled up,
**every plan proposes resetting it**, and the diff rides along on whatever PR
merges next.

Since **tfgate1 (#36)** applies Terraform automatically on merge, that is no
longer a cosmetic diff: an unrelated merge would scale capacity away from a
queued job, or terminate the instance under a running one.

**It was invisible because the value is 0 whenever the queue is idle**, which
is whenever anyone happened to look. My own baseline plan an hour earlier said
`No changes`.

## Measured (2026-09-23, read-only)

- Live prod CE `palateful-parser-spot-gpu-prod-…`: **desired 4**, min 0, max 32.
- `terraform/modules/batch/main.tf:106`: `desired_vcpus = 0`. The resource's
  `lifecycle` block has only `create_before_destroy` — **no `ignore_changes`**.
- Queue `palateful-parser-queue-prod`: **1 RUNNABLE** job.
- Plan on clean `main` (`9c626c5a`), Terraform 1.16.3, live image tags:
  ```
  # module.batch.aws_batch_compute_environment.parser_spot_gpu will be updated in-place
      ~ desired_vcpus = 4 -> 0
  Plan: 0 to add, 1 to change, 0 to destroy.
  ```

## Is the reset deliberate? No.

The config's own comments say `min_vcpus = 0 # Scale to zero when idle` and
`desired_vcpus = 0 # Start at zero`. Scaling down when idle is **Batch's** job,
via `min_vcpus`; the `desired_vcpus` literal is an initial value only. Nothing
sets it intentionally, and no automation writes it. So the fix is to stop
Terraform managing it, not to gate the reset on an idle queue.

## Acceptance criteria

- [x] `ignore_changes = [compute_resources[0].desired_vcpus]` on the compute
      environment, with the reason in a comment.
- [x] **Proven:** plan with the fix is **`No changes. Your infrastructure
      matches the configuration.`** while live desired is still **4**. Before
      the fix, the same plan showed 1 change.
- [x] Merged and **applied**, verified against a live queue.

## Technical notes

- Credit: palateful-4f found it while re-planning #38; verified here
  independently against live AWS and by plan.
- `create_before_destroy` is kept.
- This does not touch the dev CE (same module, separate state).

## Status log
- 2026-09-23T00:30 — filed and fixed in one pass; it blocks every apply in the
  lane, so it goes ahead of #39.
- 2026-09-23T01:40 — **done, and verified against the harmful condition being
  live.** Merged as `5dbb241e`. Predictions were recorded *before* the apply
  and all five held:
  1. `Affected projects: terraform`
  2. `deploy-images` skipped
  3. `terraform-prod` ran on the **deployed** tag `9c626c5a…` while HEAD was
     `5dbb241e` (the resolver returned a different tag from alrt1's apply,
     because #40 deployed in between — it reads the running task definitions
     each time, so it tracks reality rather than a constant)
  4. plan **`No changes.`**, apply **`Apply complete! Resources: 0 added, 0
     changed, 0 destroyed.`**
  5. Batch untouched: **desired 4**, min 0, **1 RUNNABLE** job
  **The failure signature (`1 changed`, `desired_vcpus 4 -> 0`) did not
  appear.** The apply ran while a job was queued and Batch had scaled up —
  the exact condition under which the old config would have taken that
  capacity away. Third Terraform-only change applied by the tfgate1 gate.
- 2026-09-23T01:40 — **the first attempt never applied.** `5dbb241e`'s first
  run failed in `setup` on a transient PyPI timeout, which skipped
  `detect-changes`, `terraform-prod` and every deploy leg. The merge looked
  landed while prod still had the old behaviour. Filed as **applygap1**: an
  apply that never ran is indistinguishable from a deploy that ran and failed.
