# Story pim-2 — RDS parameter group + Performance Insights

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** pim-1 (hard gate for pre-change baseline capture).

## Scope

Cost-neutral RDS tuning — new `aws_db_parameter_group` resource, PI
enabled, slow-query log exported to CloudWatch, predictable maintenance
window set. No instance-class change yet (that's pim-3). No reboot
triggered by this apply because `apply_immediately=false` is now the
default — static parameter values land `pending-reboot` and apply at
the next maintenance window.

## Implementation notes

- **Static vs dynamic params** enumerated in the parameter group
  resource comment. `shared_buffers` + `max_connections` = static
  (reboot required; land on pending-reboot). `work_mem`,
  `maintenance_work_mem`, `effective_cache_size`,
  `log_min_duration_statement` = dynamic (hot-apply).
- **`max_connections=80`.** Pool arithmetic option A from the epic's
  resolved open question: pool 20 + overflow 40 + 20 reserved for
  beat/worker/migrator/psql.
- **`log_min_duration_statement=100`.** Every query >100ms writes a
  row to the slow-query log. Exported via
  `enabled_cloudwatch_logs_exports=["postgresql"]` to the existing
  `/aws/rds/instance/palateful-prod-db/postgresql` log group (AWS
  default).
- **Performance Insights** enabled with 7-day retention (free tier).
  Free for 6 months on `t4g.small` — calendar reminder in `BUGS.md`
  at day 170.
- **Maintenance window = tue:07:00-tue:08:00 UTC** = midnight Pacific.
  Low-risk for single-user prod. Resolves epic open question 1.
- **`apply_immediately=false`.** Existing RDS module had
  `apply_immediately=true` hardcoded; moved to a variable with
  default `false` so static params can't trigger a surprise reboot on
  `terraform apply`. Dynamic params still hot-apply because the
  parameter group sets `apply_method=immediate` on those.
- **Parameter values are postgres-native units.** `shared_buffers` in
  8KB pages (32768 pages × 8KB = 256MB). `max_connections` in
  connections. `work_mem` + `maintenance_work_mem` in KB.
  `effective_cache_size` in 8KB pages. `log_min_duration_statement`
  in ms.
- **Rollback.** Delete `parameter_group.tf` + remove
  `parameter_group_name` from `main.tf`. Instance falls back to the
  default `postgres16` parameter group; one reboot required to
  un-apply the static params.

## File list

- `terraform/modules/rds/parameter_group.tf` [NEW]
- `terraform/modules/rds/main.tf` [MODIFY] — wire parameter group,
  maintenance window, PI, slow-query log; `apply_immediately`
  defaults flipped to `false`.

## Acceptance criteria — coverage

- AC1 ✅ `maintenance_window = "tue:07:00-tue:08:00"` on RDS module
  (via new variable with that default).
- AC2 ✅ New `aws_db_parameter_group` named
  `palateful-prod-pg16-perf`.
- AC3 ✅ Static vs dynamic explicitly annotated per parameter
  (resource-comment header + `apply_method` on every parameter
  block). Commit message mirrors.
- AC4 ✅ `performance_insights_enabled=true`, retention 7.
- AC5 ✅ `enabled_cloudwatch_logs_exports=["postgresql"]`.
- AC6 ✅ `apply_immediately=false` — default.
- AC7 — Terraform plan: not captured at story-write time (no AWS
  creds in the /dev loop). User runs `terraform plan` at deploy time
  and pastes the diff into this file if there's anything surprising.
- AC8 — Post-apply verification (`SHOW shared_buffers` etc.) is a
  user-runbook step; QA walkthrough enumerates the exact SQL.

## Follow-ups

- pim-3 upgrades `instance_class` → `db.t4g.small`. Same maintenance
  window applies.
- pim-4b (pool + ALB) cannot merge until `SHOW max_connections;`
  returns `80` in prod — gated on the reboot from this story.
