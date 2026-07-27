"""E-5 (P0) — RED artifact for the rotation-redeploy Lambda handler.

Workstream: rotation-self-heal (plan 462355), Phase 3 (FR-4a).

Expectation (`_devx/workstreams/rotation-self-heal/expectations.md:60-72`):
    When the `AWSCURRENT` label moves on the database secret, the system
    SHALL force a new deployment of both the api and worker ECS services.

Thresholds asserted here, one test apiece:
  1. `update_service` called exactly 1x per service (2 total), each with
     `forceNewDeployment=True`.
  2. A non-matching secret produces 0 calls.
  3. A partial failure names the failing service in `failed` and is
     *visible* — logged at ERROR, not swallowed.
  4. Missing required env raises rather than silently no-op'ing.
  5. AST import hygiene: stdlib ∪ {boto3, botocore} only, no relative
     imports — the module is packaged standalone by `archive_file`
     (`source_file`), so `from . import x` breaks the deploy, not the test.

This file is authored RED, before `utils/services/rotation_redeploy.py`
exists. The expected first failure is `ModuleNotFoundError` for that
module — the missing feature itself, not a wiring error.

Two event shapes are exercised deliberately. Plan T4.1 records that the
Secrets Manager `Secret Label Updated` shape is unconfirmed against a live
event, with the CloudTrail `RotationSucceeded` signal as the proven
fallback. Pinning both here means whichever shape T4.1 lands on, the
handler already matches it, and the eventual EventBridge pattern is the
only thing left to get right.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

WATCHED_ARN = (
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:rds!db-abc123-AbCdEf"
)
OTHER_ARN = (
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:some-other-secret-ZyXwVu"
)
CLUSTER = "palateful-prod"
API_SERVICE = "palateful-api-prod"
WORKER_SERVICE = "palateful-worker-prod"

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "utils"
    / "services"
    / "rotation_redeploy.py"
)

# Allowed top-level import roots for the Lambda module (T3.3). Everything
# else must come from the standard library.
ALLOWED_THIRD_PARTY = frozenset({"boto3", "botocore"})


# ---------------------------------------------------------------------------
# Event fixtures — both candidate shapes from plan T4.1
# ---------------------------------------------------------------------------


def label_updated_event(secret_arn: str) -> dict:
    """The native EventBridge `Secret Label Updated` shape (primary)."""
    return {
        "version": "0",
        "detail-type": "AWS Secrets Manager Secret Label Updated",
        "source": "aws.secretsmanager",
        "region": "us-east-1",
        "resources": [secret_arn],
        "detail": {
            "SecretId": secret_arn,
            "AddedLabels": ["AWSCURRENT"],
            "RemovedLabels": ["AWSPREVIOUS"],
        },
    }


def cloudtrail_rotation_event(secret_arn: str) -> dict:
    """The CloudTrail `RotationSucceeded` shape (proven fallback).

    Deliberately carries no top-level `resources` key — the handler must
    find the secret in `detail.additionalEventData.SecretId` too, or the
    fallback pattern T4.1 names is unusable.
    """
    return {
        "version": "0",
        "detail-type": "AWS API Call via CloudTrail",
        "source": "aws.secretsmanager",
        "region": "us-east-1",
        "detail": {
            "eventSource": "secretsmanager.amazonaws.com",
            "eventName": "RotationSucceeded",
            "additionalEventData": {"SecretId": secret_arn},
        },
    }


# ---------------------------------------------------------------------------
# Stub ECS client
# ---------------------------------------------------------------------------


class StubEcsClient:
    """Records `update_service` calls; optionally fails named services."""

    def __init__(self, fail_services: frozenset[str] = frozenset()):
        self.calls: list[dict] = []
        self._fail_services = fail_services

    def update_service(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("service") in self._fail_services:
            raise RuntimeError(f"ECS rejected update for {kwargs.get('service')}")
        return {"service": {"serviceName": kwargs.get("service")}}


@pytest.fixture
def rotation_redeploy():
    """Import the module under test.

    Kept as a fixture so the RED failure is reported per-test (a missing
    feature in every threshold) rather than as a single collection error.
    """
    from utils.services import rotation_redeploy as module

    return module


@pytest.fixture
def configured_env(monkeypatch):
    monkeypatch.setenv("ECS_CLUSTER", CLUSTER)
    monkeypatch.setenv("ECS_SERVICES", f"{API_SERVICE},{WORKER_SERVICE}")
    monkeypatch.setenv("WATCHED_SECRET_ARN", WATCHED_ARN)


@pytest.fixture
def stub_client(monkeypatch, rotation_redeploy):
    """Swap boto3's client factory for the recording stub.

    Patched on the module's own `boto3` reference, which pins the
    construction site: the handler builds its ECS client itself rather
    than accepting one, because Lambda gives it no injection point.
    """

    def _install(client: StubEcsClient) -> StubEcsClient:
        def fake_client(service_name, *args, **kwargs):
            assert service_name == "ecs", (
                f"handler should only construct an ECS client, got {service_name!r}"
            )
            return client

        monkeypatch.setattr(rotation_redeploy.boto3, "client", fake_client)
        return client

    return _install


# ---------------------------------------------------------------------------
# Threshold 1 — exactly one forced deployment per service
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_builder",
    [label_updated_event, cloudtrail_rotation_event],
    ids=["secret-label-updated", "cloudtrail-rotation-succeeded"],
)
def test_matching_secret_forces_one_deployment_per_service(
    rotation_redeploy, configured_env, stub_client, event_builder
):
    client = stub_client(StubEcsClient())

    result = rotation_redeploy.handler(event_builder(WATCHED_ARN), None)

    assert len(client.calls) == 2, (
        f"expected exactly 2 update_service calls (1 per service), "
        f"got {len(client.calls)}: {client.calls!r}"
    )
    assert [c["service"] for c in client.calls] == [API_SERVICE, WORKER_SERVICE]
    for call in client.calls:
        assert call["cluster"] == CLUSTER
        assert call["forceNewDeployment"] is True, (
            f"forceNewDeployment must be True — without it the service keeps "
            f"the old task definition and no credential is re-resolved: {call!r}"
        )

    assert sorted(result["redeployed"]) == sorted([API_SERVICE, WORKER_SERVICE])
    assert result["failed"] == []


# ---------------------------------------------------------------------------
# Threshold 2 — a non-matching secret is a no-op
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_builder",
    [label_updated_event, cloudtrail_rotation_event],
    ids=["secret-label-updated", "cloudtrail-rotation-succeeded"],
)
def test_non_matching_secret_redeploys_nothing(
    rotation_redeploy, configured_env, stub_client, event_builder
):
    client = stub_client(StubEcsClient())

    result = rotation_redeploy.handler(event_builder(OTHER_ARN), None)

    assert client.calls == [], (
        f"a rotation on an unrelated secret must not bounce production "
        f"services; got {client.calls!r}"
    )
    assert result["redeployed"] == []
    assert result["failed"] == []


def test_event_without_any_secret_identifier_redeploys_nothing(
    rotation_redeploy, configured_env, stub_client
):
    """An unrecognized event shape fails closed, not open.

    If the handler cannot find a secret identifier it must do nothing —
    redeploying on every unmatched event would turn a mis-scoped
    EventBridge rule into a deployment loop.
    """
    client = stub_client(StubEcsClient())

    result = rotation_redeploy.handler({"detail-type": "Something Else"}, None)

    assert client.calls == []
    assert result["redeployed"] == []


# ---------------------------------------------------------------------------
# Threshold 3 — partial failure is visible, not swallowed
# ---------------------------------------------------------------------------


def test_partial_failure_names_the_failing_service_and_logs_it(
    rotation_redeploy, configured_env, stub_client, caplog
):
    client = stub_client(StubEcsClient(fail_services=frozenset({WORKER_SERVICE})))
    caplog.set_level(logging.ERROR)

    result = rotation_redeploy.handler(label_updated_event(WATCHED_ARN), None)

    assert result["redeployed"] == [API_SERVICE], (
        "the service that succeeded must still be reported as redeployed — "
        "a partial failure is not a total one"
    )
    assert result["failed"] and WORKER_SERVICE in str(result["failed"]), (
        f"the failing service must be named in `failed`; got {result!r}"
    )

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, (
        "a partial failure must be visible in CloudWatch — a silent backstop "
        "is the exact failure class this workstream exists to remove"
    )
    assert any(WORKER_SERVICE in r.getMessage() for r in errors), (
        f"the ERROR log must name the failing service; "
        f"got {[r.getMessage() for r in errors]!r}"
    )


def test_first_service_failure_does_not_skip_the_second(
    rotation_redeploy, configured_env, stub_client
):
    """Aggregation, not short-circuiting.

    If the api update fails, the worker must still be attempted — the
    worker is the service whose stale credential caused the outage.
    """
    client = stub_client(StubEcsClient(fail_services=frozenset({API_SERVICE})))

    result = rotation_redeploy.handler(label_updated_event(WATCHED_ARN), None)

    assert [c["service"] for c in client.calls] == [API_SERVICE, WORKER_SERVICE]
    assert result["redeployed"] == [WORKER_SERVICE]
    assert WORKER_SERVICE not in str(result["failed"])


# ---------------------------------------------------------------------------
# Threshold 4 — missing required env raises
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing", ["ECS_CLUSTER", "ECS_SERVICES", "WATCHED_SECRET_ARN"]
)
def test_missing_required_env_raises(
    rotation_redeploy, configured_env, stub_client, monkeypatch, missing
):
    client = stub_client(StubEcsClient())
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(Exception) as excinfo:
        rotation_redeploy.handler(label_updated_event(WATCHED_ARN), None)

    assert missing in str(excinfo.value), (
        f"the error must name the missing variable so a misconfigured Lambda "
        f"is diagnosable from its first invocation; got {excinfo.value!r}"
    )
    assert client.calls == []


# ---------------------------------------------------------------------------
# Threshold 5 — AST import hygiene (T3.3)
# ---------------------------------------------------------------------------


def _top_level_import_nodes(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node


def test_module_imports_stdlib_and_boto3_only():
    """Packaged by `archive_file(source_file=...)` — one module at the zip
    root, no `utils` package around it. Anything beyond stdlib/boto3 is an
    ImportError at invocation time, which is invisible until the rotation
    that needed it.

    Asserted positively (every import must be on the allowlist) so a
    relative import or a stray dependency fails too.
    """
    assert MODULE_PATH.exists(), (
        f"{MODULE_PATH} does not exist yet — Phase 3 (T3.2) creates it"
    )

    import sys

    tree = ast.parse(MODULE_PATH.read_text(), filename=str(MODULE_PATH))
    stdlib = sys.stdlib_module_names

    offenders: list[str] = []
    for node in _top_level_import_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                offenders.append(
                    f"line {node.lineno}: relative import "
                    f"(level={node.level}, module={node.module!r})"
                )
                continue
            roots = [(node.module or "").split(".")[0]]
        else:
            roots = [alias.name.split(".")[0] for alias in node.names]

        for root in roots:
            if root and root not in stdlib and root not in ALLOWED_THIRD_PARTY:
                offenders.append(f"line {node.lineno}: {root!r}")

    assert not offenders, (
        "rotation_redeploy.py must import stdlib ∪ {boto3, botocore} only — "
        f"the Lambda zip contains this file alone. Offenders: {offenders!r}"
    )


def test_module_defines_the_pinned_lambda_handler_entrypoint():
    """The Terraform handler string is `rotation_redeploy.handler` (T3.4).

    Pinned here so Phase 4 consumes the contract rather than inventing it,
    and so renaming the function fails a test instead of a rotation.
    """
    assert MODULE_PATH.exists(), (
        f"{MODULE_PATH} does not exist yet — Phase 3 (T3.2) creates it"
    )

    tree = ast.parse(MODULE_PATH.read_text(), filename=str(MODULE_PATH))
    top_level_funcs = [
        n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert "handler" in top_level_funcs, (
        f"expected a top-level `handler` function (Lambda handler string "
        f"`rotation_redeploy.handler`); found {top_level_funcs!r}"
    )
