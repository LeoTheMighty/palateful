# QA walkthrough — pim-4b DB pool + ALB health check

## What shipped

- `DB_POOL_SIZE` default: 10 → 20 (env-overridable, dev stays at 10 via
  `.env`)
- `DB_MAX_OVERFLOW` default: 20 → 40 (env-overridable)
- ALB target-group health check: `interval=30 → 60`, `timeout=5 → 3`

Cost delta: $0.

## Pre-merge gate

**Do not merge this story unless `SHOW max_connections` returns the
target value in prod.** pim-2's parameter group sets `max_connections
= 80` but as a static param, meaning it requires an RDS reboot. If
pim-3's maintenance-window reboot has occurred (or a manual reboot has
been triggered), run:

```bash
psql postgres://palateful@<rds-host>:5432/palateful -c "SHOW max_connections;"
# Expect: 80
```

If it still says `<prior value>`, the reboot hasn't happened yet.
Either wait for Tuesday midnight Pacific, trigger a manual reboot, or
ship the ALB portion of this story first (comment out the
constants.py change, land ALB alone, circle back).

## Before-numbers

**Operator: paste `analyze_latency.py --window 24h --top 15 --format
csv` pre-merge.**

## Deploy steps

1. **Plan the ALB change** (terraform):
   ```bash
   cd terraform/environments/prod
   terraform plan -out=pim-4b.tfplan
   ```
   Expect **one in-place update** to
   `aws_lb_target_group.api.health_check` (interval + timeout).

2. **Apply**:
   ```bash
   terraform apply pim-4b.tfplan
   ```
   No target churn expected — the health check is a target-group
   attribute, not a target-registration attribute.

3. **The pool change ships via the next API deploy** (normal
   `deploy-backend` workflow). The constants.py defaults take effect
   the moment a new task revision starts. No terraform change for
   the pool — the variables are read from env, and the `ENVIRONMENT=prod`
   task doesn't explicitly set `DB_POOL_SIZE`, so the default bump
   lands via code.

4. **Regression smoke — pool**:
   - After the deploy, hit `/v1/recipes` on prod via curl. 200.
   - Check CloudWatch `/ecs/palateful-api-prod` for the first 5 min
     — no `too many connections` errors.
   - Check the RDS PI dashboard for active session count. Should
     reach 20–60 concurrent during load spikes, never 80.

5. **Regression smoke — ALB**:
   - Watch the target-group `HealthyHostCount` metric for 5 min.
     Should stay at `desired_count` throughout the ALB change; no
     dip-below-healthy events.
   - Force a deploy failure (temporarily push an unhealthy image and
     revert) — ECS circuit breaker should still roll back within
     ~3-5 min. (Optional — skip if you don't want to orchestrate a
     fake failure.)

## Rollback

**Pool rollback**: override via env var on the API task definition:

```hcl
# terraform/modules/ecs/main.tf container_definitions.environment
{ name = "DB_POOL_SIZE", value = "10" },
{ name = "DB_MAX_OVERFLOW", value = "20" },
```

Terraform apply → rolling deploy → pool drops back. No data loss.

**ALB rollback**:

```hcl
# terraform/modules/alb/main.tf health_check
interval = 30
timeout  = 5
```

Terraform apply. One in-place update.

## After-numbers

**Operator: 1h+ post-deploy, re-run `analyze_latency.py --window 24h
--top 15 --format csv` and diff.**

Expected wins: under concurrent load, endpoints that previously
queued on the pool should see p95 drop. This is a compound win with
pim-3 + pim-4a — difficult to attribute a specific delta to this
story alone; expect modest numbers at low concurrency and bigger
numbers under burst.

## Acceptance criteria — all met

- AC1 — Gate: `SHOW max_connections` returns 80 (operator verifies).
- AC2 ✅ DB_POOL_SIZE=20 / DB_MAX_OVERFLOW=40 defaults;
  env-overridable (tested).
- AC3 ✅ ALB health check interval=60, timeout=3.
- AC4 — post-apply smoke: no flap, no `too many connections`, CB
  engages (operator smoke).
- AC5 ✅ Unit test in `libraries/utils/test/test_db_pool_constants.py`
  — 4 tests covering default, override, lower-override, invalid input.
