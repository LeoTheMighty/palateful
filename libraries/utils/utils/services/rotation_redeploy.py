"""rsh103 — rotation-redeploy Lambda handler (rotation-self-heal, FR-4a).

When the `AWSCURRENT` label moves on the database secret, force a new
deployment of every ECS service named in `ECS_SERVICES` so each task
re-resolves the rotated credential.

**Packaging constraint (do not break):** rsh104 packages this file with
`data "archive_file"` using `source_file`, so the Lambda zip contains this
module alone at the zip root — no `utils` package around it. Imports are
therefore limited to the standard library plus `boto3`/`botocore`, and
relative imports are forbidden. `libraries/utils/test/test_rotation_redeploy_handler.py`
asserts that with an AST guard.

Pinned Lambda contract consumed by rsh104:
    runtime = "python3.13"
    handler = "rotation_redeploy.handler"

Required environment (read at call time, not import time):
    ECS_CLUSTER         — cluster name or ARN hosting the services
    ECS_SERVICES        — comma-separated service names, redeployed in order
    WATCHED_SECRET_ARN  — only this secret's rotation triggers a redeploy
"""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)

REQUIRED_ENV_VARS = ("ECS_CLUSTER", "ECS_SERVICES", "WATCHED_SECRET_ARN")


def _require_env(name: str) -> str:
    """Return env var `name`, raising an error that names it when absent.

    A misconfigured Lambda must be diagnosable from its first invocation
    rather than looking like a successful no-op.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set — the rotation-redeploy Lambda cannot run "
            f"without it (required: {', '.join(REQUIRED_ENV_VARS)})"
        )
    return value


def _extract_secret_arn(event: Any) -> str | None:
    """Pull the secret identifier out of either supported event shape.

    Returns `None` when neither shape matches — the caller fails closed on
    that, because redeploying on an unrecognized event would turn a
    mis-scoped EventBridge rule into a deployment loop.
    """
    if not isinstance(event, dict):
        return None

    # Native EventBridge `Secret Label Updated`: ARN in `resources[]`.
    resources = event.get("resources")
    if isinstance(resources, list):
        for resource in resources:
            if isinstance(resource, str) and resource:
                return resource

    detail = event.get("detail")
    if not isinstance(detail, dict):
        return None

    secret_id = detail.get("SecretId")
    if isinstance(secret_id, str) and secret_id:
        return secret_id

    # CloudTrail `RotationSucceeded` fallback — no top-level `resources`.
    additional = detail.get("additionalEventData")
    if isinstance(additional, dict):
        secret_id = additional.get("SecretId")
        if isinstance(secret_id, str) and secret_id:
            return secret_id

    return None


def _normalize_arn(arn: str) -> str:
    """Drop Secrets Manager's trailing 6-character uniqueness suffix.

    The same secret is referred to both with and without the `-AbCdEf`
    suffix depending on whether the ARN came from an event or from a
    Terraform attribute; comparing the normalized forms matches both
    without loosening into a prefix match.
    """
    head, sep, tail = arn.rpartition("-")
    if sep and len(tail) == 6 and tail.isalnum():
        return head
    return arn


def _matches_watched_secret(candidate: str, watched: str) -> bool:
    return _normalize_arn(candidate) == _normalize_arn(watched)


def handler(event: Any, context: Any) -> dict:
    """Force a new deployment of each configured ECS service.

    Returns `{"redeployed": [...], "failed": [...]}`. Every service is
    attempted — a failure on the first does not skip the rest, because the
    worker (usually last) is the service whose stale credential caused the
    outage in the first place.
    """
    cluster = _require_env("ECS_CLUSTER")
    services = [s.strip() for s in _require_env("ECS_SERVICES").split(",") if s.strip()]
    watched_arn = _require_env("WATCHED_SECRET_ARN")

    secret_arn = _extract_secret_arn(event)
    if secret_arn is None:
        logger.warning(
            "rotation-redeploy: no secret identifier in event, ignoring "
            "(detail-type=%r)",
            event.get("detail-type") if isinstance(event, dict) else None,
        )
        return {"redeployed": [], "failed": []}

    if not _matches_watched_secret(secret_arn, watched_arn):
        logger.info(
            "rotation-redeploy: %s is not the watched secret, ignoring", secret_arn
        )
        return {"redeployed": [], "failed": []}

    ecs = boto3.client("ecs")

    redeployed: list[str] = []
    failed: list[dict] = []
    for service in services:
        try:
            ecs.update_service(
                cluster=cluster, service=service, forceNewDeployment=True
            )
        except Exception as exc:  # noqa: BLE001 — aggregate, don't short-circuit
            logger.error(
                "rotation-redeploy: forced deployment FAILED for service %s "
                "on cluster %s: %s",
                service,
                cluster,
                exc,
            )
            failed.append({"service": service, "error": str(exc)})
        else:
            logger.info(
                "rotation-redeploy: forced new deployment of %s on %s",
                service,
                cluster,
            )
            redeployed.append(service)

    return {"redeployed": redeployed, "failed": failed}
