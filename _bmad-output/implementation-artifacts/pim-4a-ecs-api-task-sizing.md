# Story pim-4a — ECS API task cpu/memory bump

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** pim-1 (baseline). Independent of pim-2/pim-3 beyond
timing — land this in a separate rolling deploy for a clean rollback
surface.

## Scope

Bump the API task definition from `cpu=256 memory=512` →
`cpu=512 memory=1024`. Removes CPU-starvation during Auth0 JWT verify
concurrent with DB queries; cuts GC pauses on task startup.

Cost delta: ≈ +$5/mo.

## Implementation notes

- Hardcoded `cpu=256 memory=512` in the ECS module replaced with
  `api_task_cpu` + `api_task_memory` variables (default 512/1024) so
  the change is one terraform apply away from reversible.
- Worker task unchanged — it already runs at 512/1024 and the worker
  queue isn't the bottleneck.
- Migrator task unchanged — one-off task.
- Rolling deploy semantics: ECS task-definition change → new revision
  is registered → service scheduler starts a new task → drains the
  old. `deployment_minimum_healthy_percent=0` +
  `deployment_maximum_percent=200` (already configured) allows
  parallel scheduling; `deployment_circuit_breaker.enable=true` +
  `rollback=true` reverts to the prior revision if the new task fails
  health checks.
- No env-var or secret changes; no app code change required.

## File list

- `terraform/modules/ecs/main.tf` [MODIFY] — replace hardcoded
  cpu/memory with variables; add `api_task_cpu` + `api_task_memory`
  variable declarations.

## Acceptance criteria — coverage

- AC1 ✅ `cpu=512`, `memory=1024` on the API task definition (as the
  variable defaults).
- AC2 — Rolling deploy: verified by operator via the CloudWatch log
  stream + ECS events timeline (no task churn beyond normal).
- AC3 — Post-apply: p99 CPU < 80% under normal load; no OOM-kill
  events in CloudWatch (operator step).
- AC4 — Rollback: flip vars back to 256/512; one terraform apply.

## Follow-ups

- pim-4b lands the pool + ALB changes after pim-2's reboot confirms
  `SHOW max_connections=80`.
