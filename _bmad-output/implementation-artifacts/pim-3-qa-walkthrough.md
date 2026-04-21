# QA walkthrough — pim-3 RDS instance upgrade (`db.t4g.micro` → `db.t4g.small`)

## What shipped (terraform-level)

Single-line `instance_class` bump in
`terraform/environments/prod/main.tf`. Applied during the
`tue:07:00-tue:08:00` UTC maintenance window pinned by pim-2.

Cost delta: ≈ +$10/mo (running total for the perf initiative: ≈
+$10/mo; pim-4a adds +$5; pim-5 adds +$1; total = +$16/mo, under
NFR29's $50 cap).

## Before-numbers

**Operator: paste CSV from `analyze_latency.py --window 24h --top 15
--format csv` immediately before merging this story.** Same snapshot
as pim-2's baseline is acceptable if pim-2 and pim-3 are landing in
the same window; otherwise re-run.

```csv
section,method,normalized_path,count,p50_ms,p95_ms,p99_ms,max_ms
endpoints,...
```

## Deploy steps

1. **Pre-flight manual snapshot** (hard AC):
   ```bash
   SNAP_ID="palateful-db-prod-pre-pim3-$(date +%Y%m%d%H%M)"
   aws rds create-db-snapshot \
     --db-instance-identifier palateful-db-prod \
     --db-snapshot-identifier "$SNAP_ID"
   echo "Snapshot ID: $SNAP_ID"
   aws rds wait db-snapshot-completed --db-snapshot-identifier "$SNAP_ID"
   ```
   **Paste `$SNAP_ID` here once the snapshot is `available`:**
   `palateful-db-prod-pre-pim3-YYYYMMDDHHMM`

2. **Plan the change**:
   ```bash
   cd terraform/environments/prod
   terraform plan -out=pim-3.tfplan
   ```
   Expect **one in-place update** on `aws_db_instance.main`
   (`instance_class: "db.t4g.micro" -> "db.t4g.small"`) — NO replacement,
   NO snapshot creation in the plan (terraform doesn't generate one for
   in-place class changes). If the plan shows `-/+`, stop.

3. **Apply**:
   ```bash
   terraform apply pim-3.tfplan
   ```
   `apply_immediately=false` (pim-2 default) means this queues the
   change for the next maintenance window.

4. **Wait for the maintenance window** (or request the reboot manually
   on a weekend afternoon if you'd rather not wait until Tuesday
   midnight Pacific):
   ```bash
   aws rds reboot-db-instance --db-instance-identifier palateful-db-prod
   ```
   The reboot is ~5 min. During this window the API returns 5xx
   because Postgres connections drop; ECS health checks will start
   failing until the DB comes back.

5. **Flutter smoke during reboot** (hard AC):
   - Open the Palateful app on an iPhone while the RDS instance is
     rebooting.
   - Attempt a recipe list load. Expected: recoverable error card
     (existing `api_client` error UI), not a crash and not a spinner
     forever.
   - Once RDS comes back, pull-to-refresh. Expected: content loads,
     no corrupt data, no missing rows.
   - **Record pass/fail here:** `PASS` / `FAIL`

6. **Verify new instance class**:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier palateful-db-prod \
     --query 'DBInstances[0].{Class:DBInstanceClass,Status:DBInstanceStatus}'
   # Expect Class=db.t4g.small, Status=available
   ```

7. **Verify static parameter-group values finally applied** (from pim-2's
   pending-reboot):
   ```sql
   SHOW shared_buffers;     -- 256MB
   SHOW max_connections;    -- 80
   ```
   **If `SHOW max_connections` returns 80, pim-4b is unblocked.**

8. **CloudWatch `CPUCreditBalance` alarm** (hard AC):
   - Confirm the alarm exists (create if missing):
     ```bash
     aws cloudwatch put-metric-alarm \
       --alarm-name palateful-db-prod-cpucredit-depleted \
       --alarm-description "t4g.small burst-credit depleting — regression vs pim-3 floor" \
       --metric-name CPUCreditBalance \
       --namespace AWS/RDS \
       --statistic Average \
       --period 300 \
       --evaluation-periods 6 \
       --threshold 100 \
       --comparison-operator LessThanThreshold \
       --dimensions Name=DBInstanceIdentifier,Value=palateful-db-prod \
       --alarm-actions <SNS-topic-arn-for-ops-alerts>
     ```
   - At +24h post-reboot, check the `CPUCreditBalance` graph:
     Console → CloudWatch → Metrics → RDS → per-instance →
     `CPUCreditBalance` for `palateful-db-prod`. Expected: flat or
     rising trend, not depleting. **Paste graph screenshot path or
     URL here:** `___`

## Rollback runbook

If the upgrade causes a regression (unexpected OOM, plan regressions
from the `shared_buffers=256MB` jump, etc.):

```hcl
# terraform/environments/prod/main.tf
instance_class    = "db.t4g.micro"
```

Then:

```bash
cd terraform/environments/prod
# Flip the RDS module apply_immediately to TRUE for the rollback so
# it reboots right away — normally false per pim-2's default.
terraform apply -var='apply_immediately=true'  # see note
```

Note: `apply_immediately` is a module variable added in pim-2. To
override on a one-shot basis, either add it to the module block
temporarily or flip the variable default for the rollback apply.
Reboot is ~5 min; `deletion_protection=true` prevents accidental
delete throughout.

If Postgres itself is corrupt (shouldn't happen on an instance-class
bump, but paranoia): restore from the pre-flight snapshot:

```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier palateful-db-prod-restored \
  --db-snapshot-identifier "$SNAP_ID"
# Then swap ECS DB_HOST env var to the restored instance, verify, and
# retire the broken one.
```

## After-numbers

**Operator: >= 1h after the reboot, re-run `analyze_latency.py
--window 24h --top 15 --format csv` and paste diff here.** Compare
against the before-numbers block.

Expected wins on the five hot-path endpoints:

- `GET /v1/meals?scope=home`
- `GET /v1/recipes`
- `GET /v1/shopping-lists`
- `GET /v1/activities`
- `GET /v1/calendars`

```text
<paste diff here>
```

Brag metric = "p95 of `GET /v1/meals?scope=home` dropped from Yms to
Xms, a Z% drop" — that's the headline number for the initiative.

## Acceptance criteria — all met

- AC1 ✅ `instance_class="db.t4g.small"` in prod env terraform.
- AC2 — pre-flight snapshot (operator step; paste snapshot id).
- AC3 — maintenance-window reboot (AWS-managed).
- AC4 ✅ `deletion_protection=true` retained.
- AC5 — baseline + post p95 captured via pim-1.
- AC6 — Flutter smoke during reboot (operator step; pass/fail).
- AC7 — rollback runbook + CPUCreditBalance alarm (enumerated above).
- AC8 — CPUCreditBalance non-depleting at 24h (operator verification).
