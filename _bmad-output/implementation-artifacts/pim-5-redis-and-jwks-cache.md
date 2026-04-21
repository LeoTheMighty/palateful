# Story pim-5 — Redis + Auth0 JWKS cache

**Status:** done
**Epic:** epic-perf-infra-and-measurement
**Depends on:** pim-1 (baseline). Independent of pim-2/pim-3/pim-4 —
can ship in parallel. Fail-open semantics mean a broken Redis can't
break the API.

## Scope

Three pieces:

1. **Terraform** — new `elasticache` module (one `cache.t4g.micro`
   node, single-AZ, SG gated to the existing ECS SG on 6379,
   at-rest-encryption on, transit-encryption off for now). SSM
   SecureString parameter holds the generated REDIS_URL; ECS
   execution role gets `ssm:GetParameters` + `kms:Decrypt` to read
   it; API + worker tasks read it as a task secret.
2. **`redis_client.py`** — async `redis.asyncio` wrapper with
   fail-open semantics. `get_redis()` returns `None` when Redis is
   unreachable; `safe_get`/`safe_set` return `None`/`False` on any
   error. Aggressive timeouts (100ms connect / 50ms op) — anything
   slower is a failure mode we'd rather fail open on.
3. **`auth0.py`** — JWKS cache relocated from module-global `_jwks:
   dict` to a three-tier read-through (in-memory → Redis → Auth0).
   1h hard TTL / 50m soft TTL. Stale-but-present serves the cached
   value and schedules a background refresh. Single-flight
   `asyncio.Lock` dedupes concurrent cold fetches inside one task.

## Implementation notes

- **Lock scope is per-verifier instance**, which in practice is
  per-task because `_verifier` is a module-global populated by
  `get_auth0_verifier()`. This is sufficient for the "five parallel
  cold-start requests in one task hit Auth0 once" guarantee. It
  does NOT dedupe across tasks (different processes, different
  locks) — Redis is the cross-task coordinator, and a five-task
  cold-start hits Redis five times but hits Auth0 once (the winner
  populates Redis before the other four check).
- **Stale-but-present semantics**: serving a soft-expired value
  while scheduling a background refresh guarantees the hard TTL
  boundary is never hit during a live request. The refresh uses
  the same `_fetch_lock` so it can't stampede either.
- **Redis value shape**: `{"jwks": {...}, "fetched_at": <epoch>}`.
  Storing the fetched-at timestamp alongside the blob is what lets
  us evaluate freshness even when reading a value written by
  another task. Redis hard TTL (`ex=3600`) is a backstop; the
  in-blob timestamp is load-bearing.
- **Fail-open on Redis**: every Redis op is wrapped; connect/
  timeout/OS/generic errors all collapse to "Redis unavailable —
  use in-memory." `Auth0Verifier` never raises because of Redis.
- **Corrupt-value handling**: `_try_parse_redis_value` returns
  `None` on any JSON/shape failure, so a malformed key self-heals
  on the next fetch.
- **ECS secret wiring**: `REDIS_URL` is pulled via SSM SecureString
  `valueFrom`. The execution role needs `ssm:GetParameters` (not
  `secretsmanager:GetSecretValue`) + `kms:Decrypt` scoped to the SSM
  KMS service. Added as a separate policy resource so rollback is
  scoped; removing the SSM parameter ARN from the module call takes
  the permission with it.
- **Dependency**: `redis = "^5.0"` added to `libraries/utils/pyproject.toml`.
  Lock regenerated via `npx nx run utils:lock`.
- **Legacy compatibility**: `get_jwks()`, `get_auth0_public_key()`,
  and `clear_jwks_cache()` module-level helpers retained unchanged
  for any existing callers. They route through the new verifier.

## File list

- `libraries/utils/pyproject.toml` [MODIFY] — add `redis = "^5.0"`
- `libraries/utils/poetry.lock` [MODIFY] — regenerated
- `libraries/utils/utils/services/redis_client.py` [NEW]
- `libraries/utils/utils/services/auth0.py` [MODIFY] — three-tier
  cache, single-flight, stale-but-present
- `services/api/tests/test_redis_client.py` [NEW] — 14 tests
- `services/api/tests/test_auth0_jwks_cache.py` [NEW] — 11 tests
  covering in-memory-fresh, stale-but-present, hard-TTL, Redis-hit,
  corrupt-Redis-blob, single-flight, fail-open, clear-cache
- `terraform/modules/elasticache/main.tf` [NEW]
- `terraform/modules/elasticache/variables.tf` [NEW]
- `terraform/modules/elasticache/outputs.tf` [NEW]
- `terraform/modules/ecs/main.tf` [MODIFY] — optional
  `redis_url_ssm_parameter_arn` var + conditional REDIS_URL secret
  on both API + worker tasks
- `terraform/modules/iam/main.tf` [MODIFY] — new
  `ssm_secure_parameter_arns` var + `ecs_execution_ssm` policy +
  `data.aws_region.current`
- `terraform/environments/prod/main.tf` [MODIFY] — wire the
  elasticache module, plumb SSM ARN to IAM + ECS modules

## Acceptance criteria — coverage

- AC1 ✅ Terraform creates `cache.t4g.micro` ElastiCache + writes
  `REDIS_URL` to SSM; SG allows API + worker (shared ECS SG) in on
  6379.
- AC2 ✅ `redis_client.py` exposes `get_redis()` → client or None;
  unit tests cover connect-refused, op-timeout, None return. Plus
  `safe_get` + `safe_set` fail-open.
- AC3 ✅ `Auth0.get_jwks()` (via `_get_jwks()`) reads Redis first;
  falls back to in-memory on Redis miss/timeout; never raises.
- AC4 ✅ 1h hard TTL / 50m soft TTL. Stale-but-present hit serves
  cached value + triggers async refresh — test
  `test_serves_stale_and_triggers_background_refresh`.
- AC5 ✅ Single-flight: test
  `test_concurrent_cold_fetches_dedupe` launches 5 parallel cold
  fetches, asserts `fetch_count == 1`.
- AC6 — **Prod canary**: operator step. After initial deploy,
  temporarily flip `redis_url_ssm_parameter_arn` to a broken value
  (or point REDIS_URL to `redis://nonexistent:6379`) for 10 min,
  confirm zero 5xx on auth-dependent endpoints. Revert.
- AC7 — Post-deploy: JWT-verify p95 drops on first-request-per-task
  for auth-dependent endpoints — captured via pim-1 for any
  `authenticate_user`-dependent path. Operator pastes into QA.

## Follow-ups

- pim-6 audits legacy migrations for non-CONCURRENTLY indexes.
- If Redis scope expands beyond JWKS (application caching, session
  state, etc.), revisit multi-AZ + transit encryption.
- Day-170 calendar reminder in BUGS.md covers PI; no equivalent
  needed here (ElastiCache has no free-tier expiry).
