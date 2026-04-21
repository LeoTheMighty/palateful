# Story pim-3 — RDS instance upgrade `db.t4g.micro` → `db.t4g.small`

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** pim-1 (baseline capture), pim-2 (parameter group +
maintenance_window live so the reboot window is pinned).

## Scope

One-line terraform change: bump `instance_class` on the prod RDS
module from `db.t4g.micro` → `db.t4g.small`. The biggest single
lever in the Performance Health Initiative — removes burst-credit
exhaustion and adds a second vCPU.

Cost delta: ≈ +$10/mo.

## Implementation notes

- `instance_class="db.t4g.small"` in
  `terraform/environments/prod/main.tf`.
- `deletion_protection=true` retained (`var.environment == "prod"`
  keeps it on in the module).
- `apply_immediately=false` (default from pim-2) — the upgrade lands
  on the next `tue:07:00-tue:08:00` UTC maintenance window.
- **No module code change**: the instance-class variable was already
  exposed; pim-3 is a single-line env-level change.
- **Pre-flight snapshot is an operator step** (not codified in
  terraform): per resolved open question, take a manual RDS snapshot
  before the maintenance window so rollback can restore a known-good
  point-in-time if the upgrade pathology-crashes.

## File list

- `terraform/environments/prod/main.tf` [MODIFY] — single-line
  `instance_class` bump + accompanying comment.

## Acceptance criteria — coverage

- AC1 ✅ `instance_class="db.t4g.small"`.
- AC2 — **Pre-flight snapshot**: operator runs `aws rds
  create-db-snapshot` before the maintenance window; snapshot id
  pasted into the QA walkthrough.
- AC3 — Maintenance-window reboot: AWS-managed, landed on
  `tue:07:00-tue:08:00` UTC (pim-2 set this).
- AC4 ✅ `deletion_protection=true` retained.
- AC5 — Baseline + post-upgrade p95 captured via pim-1 for the five
  hot-path endpoints (operator pastes into QA walkthrough).
- AC6 — Flutter smoke during reboot: operator confirms recoverable
  error card, no crash loop, no silent data loss.
- AC7 — Rollback runbook + `CPUCreditBalance < 100` CloudWatch alarm:
  enumerated in QA walkthrough.
- AC8 — `CPUCreditBalance` graph post-apply: operator verifies
  non-depleting at +24h.

## Follow-ups

- pim-4a lands the ECS API task bump in a separate rolling deploy.
- pim-4b (pool + ALB) can merge only after the maintenance-window
  reboot has occurred and `SHOW max_connections=80` is confirmed in
  prod.
