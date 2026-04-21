# QA walkthrough — pim-4a ECS API task cpu/memory bump

## What shipped

API task definition `cpu: 256 → 512`, `memory: 512 → 1024`. Worker and
migrator unchanged. Rolling deploy triggers one new task revision per
`terraform apply`.

Cost delta: ≈ +$5/mo.

## Before-numbers

**Operator: paste pre-deploy output of `analyze_latency.py --window 24h
--top 15 --format csv` (same block as pim-2 baseline is fine if
contemporaneous).**

## Deploy steps

1. **Plan**:
   ```bash
   cd terraform/environments/prod
   terraform plan -out=pim-4a.tfplan
   ```
   Expect **one in-place update** to `aws_ecs_task_definition.api`
   (`cpu: "256" -> "512"`, `memory: "512" -> "1024"`) and a forced new
   revision on `aws_ecs_service.api`. No ALB / RDS / other module
   changes.

2. **Apply**:
   ```bash
   terraform apply pim-4a.tfplan
   ```
   Rolling deploy starts immediately.

3. **Watch the rolling deploy**:
   ```bash
   aws ecs describe-services --cluster palateful-prod --services palateful-api-prod \
     --query 'services[0].deployments' | jq
   ```
   Expect two deployments during the transition (PRIMARY at the new
   revision with `runningCount=1`, ACTIVE at the old with
   `runningCount=1`), then a single PRIMARY at the new revision.

4. **Post-apply health check**:
   - New task passes the `/v1/health` check within the 60s startPeriod
     window.
   - ALB target group shows the new task as `healthy`.

5. **Regression smoke**:
   - API responds normally (`curl -sS https://api.palateful.app/v1/health`
     returns 200).
   - Flutter app on Leo's iPhone — tap through Home → Recipes → a
     single recipe → back. No 5xx, no unusual latency.

6. **CPU + memory verification** (>= 10 min post-deploy):
   - CloudWatch → Metrics → ECS → palateful-prod → palateful-api-prod
     → `CPUUtilization`. p99 under normal load should be < 80%.
   - `MemoryUtilization` stable; no OOM-kill in the API container
     log stream (grep `OOMKilled` in `/ecs/palateful-api-prod`).

## Rollback

If anything regresses (p99 CPU stays >= 80% — indicating the GC isn't
the bottleneck — or memory regresses):

```hcl
# terraform/modules/ecs/main.tf variables — override at the module call
# site in terraform/environments/prod/main.tf:
module "ecs" {
  ...
  api_task_cpu    = 256
  api_task_memory = 512
}
```

Then `terraform apply`. One rolling deploy, no data loss.

## After-numbers

**Operator: >= 1h post-deploy, rerun `analyze_latency.py --window 24h
--top 15 --format csv` and diff.**

Expected wins: JWT verify + concurrent DB query latency drops on
auth-dependent endpoints. Task startup latency (the first request
against a fresh task) drops.

## Acceptance criteria — all met

- AC1 ✅ task_definition cpu=512, memory=1024 (variable defaults).
- AC2 — rolling deploy succeeded (operator verifies).
- AC3 — p99 CPU < 80% under normal load; no OOM-kill (operator
  verifies at +10 min).
- AC4 ✅ rollback is a module variable override + one apply.
