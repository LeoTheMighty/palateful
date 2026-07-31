---
hash: rsh103
type: dev
created: 2026-07-27T12:32:00-06:00
title: Rotation-redeploy Lambda handler — pure, unit-testable Python
from: plan/plan-462355-2026-07-27T10:51-rotation-self-heal.md
status: done
owner: /devx-loop-2026-07-31T15-54-01-442-22311
branch: feat/dev-rsh103
---

## Goal

The rotation-redeploy handler as pure, unit-testable Python — separated from
its infrastructure (rsh104) so E-5's thresholds are provable without an AWS
round-trip. On an `AWSCURRENT` label move it forces a new deployment of both
ECS services.

**Deadline: 2026-07-29.**

## Acceptance criteria

- [ ] `libraries/utils/utils/services/rotation_redeploy.py` exists with a
      top-level `handler(event, context) -> dict` returning
      `{"redeployed": [...], "failed": [...]}`.
- [ ] `update_service` called **exactly 1 time per service** (2 calls total),
      each with `cluster` and `forceNewDeployment=True`.
- [ ] A non-matching secret ARN produces **0** calls; an unrecognized event
      shape also produces 0 calls (fail closed, so a mis-scoped EventBridge
      rule cannot become a deployment loop).
- [ ] Both candidate event shapes match: the native EventBridge
      `Secret Label Updated` (ARN in `resources[]` / `detail.SecretId`) **and**
      the CloudTrail `RotationSucceeded` fallback (ARN in
      `detail.additionalEventData.SecretId`, no `resources` key). rsh104's T4.1
      picks one; the handler must already tolerate whichever it is.
- [ ] A partial failure names the failing service in `failed`, still reports
      the succeeding one in `redeployed`, **and logs at ERROR** naming the
      failing service — partial failure must be visible, not swallowed.
- [ ] A first-service failure does **not** skip the second (aggregate, don't
      short-circuit).
- [ ] Missing `ECS_CLUSTER` / `ECS_SERVICES` / `WATCHED_SECRET_ARN` raises,
      naming the missing variable, rather than silently no-op'ing.
- [ ] **AST guard**: every top-level import in `rotation_redeploy.py` resolves
      to stdlib or `boto3`/`botocore`, asserted positively, with relative
      imports rejected.
- [ ] The pinned Lambda contract — runtime `python3.13`, handler string
      `rotation_redeploy.handler` — is recorded in this status log so rsh104
      consumes it rather than inventing it.
- [ ] `poetry run pytest libraries/utils/` passes.

## Technical notes

- **Hard constraint: stdlib + boto3/botocore only.** No `utils` internal
  imports, no relative imports, no other third-party packages — even though
  the file lives inside the `utils` package. rsh104 packages it with
  `data "archive_file"` using `source_file`, so the zip contains exactly this
  one module at the zip root. A `from . import x` breaks the deploy, not the
  test.
- Env config is read **at call time**, not import time — the tests
  monkeypatch it per case.
- The ECS client is constructed by the handler itself via `boto3.client("ecs")`
  (Lambda offers no injection point); tests patch
  `rotation_redeploy.boto3.client`.
- The action itself is already proven: `deploy-services` runs
  `aws ecs update-service --force-new-deployment` (`ci.yml:902`).
- Precedent for AST-based import guards:
  `libraries/utils/test/test_async_engine_guard.py` and
  `test_database_api_frozen.py` — follow it.
- Parallel-safe with rsh101 and rsh102 (disjoint files; no deploy-lane
  dependency — this story is unit-tested only).
- RED artifact (do **not** re-author):
  `libraries/utils/test/test_rotation_redeploy_handler.py` (E-5).
- Full context: `_devx/workstreams/rotation-self-heal/plan.md` §Phase 3.

## Status log

- 2026-07-27T12:32 — emitted from plan 462355 at RED-gate PASS. E-5 observed
  RED right-reason (`ModuleNotFoundError: utils.services.rotation_redeploy`,
  plus explicit module-absent assertions in the AST guards); see
  `_devx/workstreams/rotation-self-heal/evals/RED-report.md`.
- 2026-07-31T09:54:01-06:00 — claimed by /devx in session /devx-loop-2026-07-31T15-54-01-442-22311
- 2026-07-31T15:57:28.239Z — loop iteration 1: Implemented libraries/utils/utils/services/rotation_redeploy.py, turning the rsh103 RED artifact fully GREEN (12/12) with the whole utils suite passing at 620 tests.
  - Change: Added `libraries/utils/utils/services/rotation_redeploy.py`: a stdlib+boto3-only Lambda module with a top-level `handler` that forces one `update_service(..., forceNewDeployment=True)` per configured ECS service, aggregates rather than short-circuits on failure, logs failures at ERROR naming the service, and returns `{redeployed, failed}`.
  - Change: Secret matching handles both candidate event shapes (EventBridge `resources[]`/`detail.SecretId` and the CloudTrail `detail.additionalEventData.SecretId` fallback) and fails closed to 0 calls on unrecognized shapes or non-matching ARNs.
  - Change: Env config (`ECS_CLUSTER`, `ECS_SERVICES`, `WATCHED_SECRET_ARN`) is read at call time and raises a `RuntimeError` naming the missing variable before any ECS client is constructed.
  - Change: Removed the rsh103 line from `tools/red-artifacts.txt` so the acceptance test is back in default pytest collection (verified: 12 rotation tests collected).
  - Learning: Pinned Lambda contract for rsh104: runtime `python3.13`, handler string `rotation_redeploy.handler` — recorded in the module docstring alongside the `archive_file`/`source_file` packaging constraint.
  - Learning: The worktree has no Poetry virtualenv and `poetry install` was not needed: running the suite as `PYTHONPATH=$PWD/libraries/utils /Users/leonidbelyi/personal/palateful/.venv/bin/python -m pytest libraries/utils/` works, because PYTHONPATH precedes the main-checkout develop-install .pth entry and resolves `utils` to the worktree source. Plain `poetry run pytest` inside `libraries/utils/` instead creates a fresh empty venv and dies on `ModuleNotFoundError: utils` at conftest import.
  - Learning: Secrets Manager ARNs arrive with and without the trailing 6-char uniqueness suffix depending on source (event vs Terraform attribute); the handler normalizes that suffix off both sides rather than doing a prefix match, so rsh104 can pass either form as `WATCHED_SECRET_ARN`.
- 2026-07-31T16:11:05.381Z — phase 4: loop-shipped — per-iteration verification (see iteration lines above) stood in for the interactive self-review pass; line appended by the loop merge tail per dvx103
- 2026-07-31T16:11:05.382Z — merged via devx loop — PR https://github.com/LeoTheMighty/palateful/pull/22
