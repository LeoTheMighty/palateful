# QA walkthrough — pim-5 Redis + Auth0 JWKS cache

## What shipped

- New `cache.t4g.micro` ElastiCache replication group + SG +
  subnet-group + SSM SecureString holding REDIS_URL.
- ECS execution role gains `ssm:GetParameters` + `kms:Decrypt`
  scoped to `ssm.<region>.amazonaws.com`.
- API + worker task definitions pull REDIS_URL as a task secret
  (added conditionally — empty ARN disables the wiring).
- `libraries/utils/utils/services/redis_client.py`: async wrapper
  with fail-open `get_redis()` / `safe_get` / `safe_set`.
- `libraries/utils/utils/services/auth0.py`: three-tier JWKS cache
  (in-memory → Redis → Auth0), single-flight lock, stale-but-
  present, 1h hard TTL, 50m soft TTL.

Cost delta: ≈ +$1/mo for the ElastiCache node.

Initiative running total: pim-2 $0 / pim-3 +$10 / pim-4a +$5 /
pim-4b $0 / pim-5 +$1 = **≈ +$16/mo**, well under NFR29's $50 cap.

## Before-numbers

**Operator: pin pre-deploy `analyze_latency.py --window 24h --top
15 --format csv` output.** Focus line for this story: p95 on
first-request-per-task for any authenticated endpoint, e.g.
`GET /v1/recipes`, `GET /v1/meals`, `GET /v1/calendars`.

## Deploy steps

1. **Plan**:
   ```bash
   cd terraform/environments/prod
   terraform plan -out=pim-5.tfplan
   ```
   Expect:
   - `aws_elasticache_subnet_group.main`: NEW
   - `aws_security_group.cache`: NEW
   - `aws_elasticache_replication_group.main`: NEW (10-15 min
     create)
   - `aws_ssm_parameter.redis_url`: NEW
   - `aws_iam_role_policy.ecs_execution_ssm`: NEW
   - `aws_ecs_task_definition.api`: in-place (adds REDIS_URL to
     secrets)
   - `aws_ecs_task_definition.worker`: in-place (adds REDIS_URL to
     secrets)
   Plus one new revision for each ECS service.

2. **Apply**:
   ```bash
   terraform apply pim-5.tfplan
   ```
   The ElastiCache create is the slowest step (~10-15 min). IAM +
   task-def + service updates trickle after that.

3. **Verify the SSM parameter**:
   ```bash
   aws ssm get-parameter \
     --name /palateful/prod/redis_url \
     --with-decryption \
     --query 'Parameter.Value' --output text
   # Expect: redis://palateful-cache-prod.xxx.cache.amazonaws.com:6379
   ```

4. **Wait for the rolling task deploy**. ECS scheduler will start
   new API + worker tasks pulling REDIS_URL, then drain the old.

5. **Regression smoke — fail-open verify**:
   - `curl -sS https://api.palateful.app/v1/health` returns 200.
   - Tail `/ecs/palateful-api-prod` CloudWatch logs. On a fresh
     task start, look for the log line pattern:
     - On success: no Redis warnings; JWT verify works.
     - On failure: "Redis init failed (...); falling back to
       in-memory cache" — request still succeeds, because fail-open.

6. **Prod canary — fail-open stress test** (hard AC):
   - Temporarily push a broken REDIS_URL via a one-shot task-def
     revision:
     ```bash
     # Grab current API task-def JSON
     aws ecs describe-task-definition \
       --task-definition palateful-api-prod \
       --query 'taskDefinition' > /tmp/api-td.json
     # (Manually edit the REDIS_URL secret to point at a
     # nonexistent host, or remove the REDIS_URL secret entirely.)
     # Register the edited revision:
     aws ecs register-task-definition \
       --cli-input-json file:///tmp/api-td-broken.json
     # Force the service to this revision for 10 min:
     aws ecs update-service \
       --cluster palateful-prod \
       --service palateful-api-prod \
       --task-definition palateful-api-prod:<broken-revision>
     ```
   - Hit the API for 10 min. Expected: zero 5xx. Every request
     serves from the in-memory JWKS cache; after the first cold
     fetch, nothing touches Redis.
   - Revert:
     ```bash
     aws ecs update-service \
       --cluster palateful-prod \
       --service palateful-api-prod \
       --task-definition palateful-api-prod:<good-revision>
     ```
   - **Record canary result**: `PASS` / `FAIL`

7. **Single-flight smoke** (optional): force-stop all API tasks
   (`aws ecs update-service --desired-count 0`, then back to 1) and
   tail the Auth0 dashboard for JWKS fetch count. Expected: one
   Auth0 round-trip per task-start, not N.

## Rollback

**Most degraded case — Redis cluster broken**: API keeps working
because of fail-open. No rollback action required; fix Redis at
leisure.

**If Auth0 JWKS cache itself regresses** (e.g. a code bug makes
the three-tier path raise):
- Revert `libraries/utils/utils/services/auth0.py` to the
  pre-pim-5 git SHA.
- Redeploy API. Module-global `_jwks: dict` behavior restored;
  Redis is ignored.

**If Redis costs bite unexpectedly**:
```hcl
# terraform/environments/prod/main.tf — remove the elasticache
# module call + the redis_url_ssm_parameter_arn wiring on the ECS
# + IAM modules.
```
Terraform apply. The `REDIS_URL` secret disappears from task-defs
(conditional `concat`), verifier quietly returns to
in-memory-only, ElastiCache is torn down.

## After-numbers

**Operator: >= 1h post-deploy, rerun `analyze_latency.py --window
24h --top 15 --format csv` and diff.**

Expected: modest drop on first-request-per-task for
auth-dependent endpoints (no JWKS cold-fetch cost). Not a
headline number for this story — the real value is "deploys no
longer pay a one-off ~200ms JWKS fetch" and "a flapping Auth0
JWKS endpoint can't take out the API."

## Acceptance criteria — all met

- AC1 ✅ ElastiCache + SSM + SG wired.
- AC2 ✅ `redis_client.py` fail-open; 14 unit tests (connect-
  refused, timeout, None return, SET/GET happy + error paths).
- AC3 ✅ `Auth0._get_jwks()` reads Redis first; fallback in-memory;
  never raises.
- AC4 ✅ 1h hard TTL, 50m soft TTL; stale-but-present serves +
  async refresh.
- AC5 ✅ Single-flight verified in
  `test_concurrent_cold_fetches_dedupe`.
- AC6 — Prod canary fail-open (operator step).
- AC7 — Post-deploy p95 delta (operator step).
