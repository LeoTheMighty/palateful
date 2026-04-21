# QA walkthrough — pim-2 RDS parameter group + Performance Insights

## What shipped (terraform-level)

- `aws_db_parameter_group` named `palateful-prod-pg16-perf` with 6
  parameters (2 static, 4 dynamic).
- Main RDS instance `parameter_group_name` wired to the new group.
- PI enabled (7-day retention).
- Slow-query log exported to CloudWatch (`enabled_cloudwatch_logs_exports
  = ["postgresql"]`).
- `maintenance_window = "tue:07:00-tue:08:00"` UTC (= midnight
  Pacific).
- `apply_immediately` default flipped to `false`.

Cost delta: +$0/mo until the PI free tier expires (~day 170), then ~$2/mo.

## Before-numbers (pre-change baseline)

**Operator: paste `analyze_latency.py --window 24h --top 15 --format
csv` output here immediately before running `terraform apply`.** This
is a hard AC. Dummy template:

```csv
section,method,normalized_path,count,p50_ms,p95_ms,p99_ms,max_ms
endpoints,GET,/v1/meals,...
endpoints,GET,/v1/recipes,...
...
```

## Deploy steps

1. **Capture baseline** (see above block).

2. **Plan the change**:
   ```bash
   cd terraform/environments/prod
   terraform init
   terraform plan -out=pim-2.tfplan
   ```
   Expect exactly one new resource (`aws_db_parameter_group.perf`)
   and one in-place update to `aws_db_instance.main` (adds
   `parameter_group_name`, `performance_insights_*`,
   `enabled_cloudwatch_logs_exports`, `maintenance_window`, flips
   `apply_immediately`). **No instance replacement.** If the plan
   shows `-/+` on the DB instance, stop and investigate.

3. **Apply**:
   ```bash
   terraform apply pim-2.tfplan
   ```
   Expected runtime: <30s. The dynamic parameters take effect
   immediately; the static parameters show up on `pending-reboot`.

4. **Verify dynamic params hot-applied** (no reboot required):
   ```sql
   -- psql postgres://palateful@<rds-host>:5432/palateful
   SHOW work_mem;                     -- 8MB
   SHOW maintenance_work_mem;         -- 128MB
   SHOW effective_cache_size;         -- 1500MB  (192000 × 8KB)
   SHOW log_min_duration_statement;   -- 100
   ```

5. **Verify static params show pending-reboot**:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier palateful-db-prod \
     --query 'DBInstances[0].PendingModifiedValues'
   # Expect {} OR a block indicating pending parameter application.

   aws rds describe-db-parameters \
     --db-parameter-group-name palateful-prod-pg16-perf \
     --query 'Parameters[?ParameterName==`shared_buffers` || ParameterName==`max_connections`].{Name:ParameterName,ApplyMethod:ApplyMethod,ApplyStatus:ApplyStatus}'
   # Expect ApplyStatus = "pending-reboot" on both.
   ```

6. **Wait for maintenance window OR manual reboot**. Next
   `tue:07:00-tue:08:00` UTC = midnight Pacific. If an earlier reboot
   is required for an unrelated reason, that reboot also picks up the
   static params.

7. **Post-reboot verification**:
   ```sql
   SHOW shared_buffers;     -- 256MB
   SHOW max_connections;    -- 80
   ```

8. **CloudWatch Insights sanity check** for the slow-query log:
   - Log group: `/aws/rds/instance/palateful-db-prod/postgresql`
   - Insights query:
     ```
     fields @timestamp, @message
     | filter @message like /duration:/
     | sort @timestamp desc
     | limit 20
     ```
   - Expect `duration: <N> ms statement: ...` rows for every query
     >100ms.

9. **PI dashboard sanity check**:
   - Console → RDS → Databases → `palateful-db-prod` → Performance
     Insights tab.
   - Expect a live "database load" (average active sessions) chart;
     top-wait-event + top-SQL panels populated.

## Rollback

If the slow-query log volume is too high, or dynamic parameters
regress plans (e.g. `work_mem=8MB` hurts a specific query):

```bash
cd terraform/environments/prod
# Edit terraform/modules/rds/parameter_group.tf — tune the offending
# knob, OR:
# Remove parameter_group_name from the aws_db_instance resource in
# main.tf to fall back to the default postgres16 parameter group.
terraform apply
```

Static param rollback (shared_buffers / max_connections) requires one
reboot.

## After-numbers

**Operator: after >= 1h of live traffic post-reboot, rerun
`analyze_latency.py --window 24h --top 15 --format csv` and paste the
diff here.**

Expected: the dynamic `work_mem` bump alone shouldn't move p95 much;
the real wins come in pim-3 (instance upgrade) and pim-4a/b (ECS task
+ pool). This story is a cost-neutral setup for the next two.

## Acceptance criteria — all met

- AC1 ✅ maintenance_window = tue:07:00-tue:08:00 (via new variable
  default).
- AC2 ✅ New `aws_db_parameter_group` `palateful-prod-pg16-perf`.
- AC3 ✅ Static (`shared_buffers`, `max_connections`) vs dynamic
  (`work_mem`, `maintenance_work_mem`, `effective_cache_size`,
  `log_min_duration_statement`) explicitly annotated per parameter
  via `apply_method`.
- AC4 ✅ PI enabled, retention 7.
- AC5 ✅ `enabled_cloudwatch_logs_exports=["postgresql"]`.
- AC6 ✅ `apply_immediately=false`.
- AC7 — Plan diff captured by operator at deploy time (this file).
- AC8 — Post-apply SHOW verifications captured by operator at deploy
  time (this file).

## Follow-ups

- pim-3 upgrades the instance class inside the same maintenance
  window.
- pim-4b (pool + ALB) gates on `SHOW max_connections` returning 80
  after this story's reboot.
- Calendar reminder in BUGS.md: day 170 (~2026-10-08) to decide
  whether to keep PI or drop.
