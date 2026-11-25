"""E-6 (shk101) — the server serves the shake ring and accepts the trigger.

expectations.md E-6 threshold:
  * `GET /v1/flags/perf` carries `shake_report` equal to the configured
    value, `admins` when `SHAKE_REPORT_RING` is unset;
  * an invalid value fails settings validation at startup;
  * feedback `context.trigger` of `shake` / `profile` is stored, absent
    stores none, `wiggle` is a 422 that writes no row.

Plus one cross-check the threshold implies but no API test can reach on its
own: the variable terraform writes is the one `Settings` reads, and both
accept the same three values. The ring exists so it can be turned off; a
ring whose env var name drifted from the setting would serve `admins`
forever and no response-level test would notice.

On unfixed code (the workstream base, before shk101) every test here fails
except `test_absent_trigger_stores_none`, which is a regression guard for
clients that send no trigger and is meant to pass on both. The per-test
reading is in the shk101 PR body.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import get_args
from unittest.mock import patch

import pytest

_RINGS = ("off", "admins", "everyone")

# Required fields Settings refuses to start without; everything else is
# left to defaults so the ring's own default is what gets measured.
_REQUIRED_ENV = {
    "AUTH0_DOMAIN": "test.auth0.com",
    "AUTH0_AUDIENCE": "https://api.palateful.test",
    "DATABASE_URL": "postgresql://t@localhost/t",
}


def _settings_from_env(**ring_env: str):
    """Build a real Settings from the process environment — the path the
    ECS task takes — with SHAKE_REPORT_RING set only if given."""
    from config import Settings

    env = {k: v for k, v in os.environ.items() if k != "SHAKE_REPORT_RING"}
    env.update(_REQUIRED_ENV)
    env.update(ring_env)
    with patch.dict(os.environ, env, clear=True):
        # _env_file=None: a developer's services/api/.env must not decide
        # what "unset" means.
        return Settings(_env_file=None)


# ---------------------------------------------------------------------------
# Flags: the ring, end to end from the environment variable
# ---------------------------------------------------------------------------


class TestShakeRingSetting:
    def test_unset_defaults_to_admins(self):
        s = _settings_from_env()
        assert s.shake_report_ring == "admins"

    @pytest.mark.parametrize("ring", _RINGS)
    def test_env_var_sets_the_ring(self, ring):
        s = _settings_from_env(SHAKE_REPORT_RING=ring)
        assert s.shake_report_ring == ring

    @pytest.mark.parametrize("bad", ["wiggle", "Admins", "ADMINS", "", " off"])
    def test_invalid_value_fails_startup(self, bad):
        """Fails closed at startup rather than serving a guess. Case and
        whitespace variants are included because a hand-typed terraform
        edit is how a bad value arrives."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as excinfo:
            _settings_from_env(SHAKE_REPORT_RING=bad)
        assert "shake_report_ring" in str(excinfo.value)


class TestFlagsServeTheRing:
    def test_default_response_carries_admins(self, unauthed_client):
        """With no override, the live settings object answers `admins` —
        the conftest environment sets no SHAKE_REPORT_RING."""
        assert "SHAKE_REPORT_RING" not in os.environ
        response = unauthed_client.get("/v1/flags/perf")
        assert response.status_code == 200
        assert response.json()["shake_report"] == "admins"

    @pytest.mark.parametrize("ring", _RINGS)
    def test_response_carries_the_configured_ring(self, unauthed_client, ring):
        configured = _settings_from_env(SHAKE_REPORT_RING=ring)
        with patch("api.v1.flags.get_perf_flags.settings", configured):
            response = unauthed_client.get("/v1/flags/perf")
        assert response.status_code == 200
        body = response.json()
        assert body["shake_report"] == ring
        # The latency kill-switch beside it is untouched.
        assert body["ingest_enabled"] is True
        assert body["sampling_rate"] == 1.0


# ---------------------------------------------------------------------------
# Terraform writes the variable Settings reads
# ---------------------------------------------------------------------------

_REPO = Path(__file__).resolve().parents[3]
_ECS_MODULE = _REPO / "terraform" / "modules" / "ecs" / "main.tf"
_PROD_ENV = _REPO / "terraform" / "environments" / "prod" / "main.tf"


def _container_block(tf: str, name: str) -> str:
    """Text of one container definition: from its `name = "<name>"` line
    to the next container's. The module defines api, worker, migrator in
    that order."""
    starts = [
        (m.group(1), m.start())
        for m in re.finditer(r'^\s+name\s+=\s+"(api|worker|migrator)"\s*$', tf, re.M)
    ]
    names = [n for n, _ in starts]
    assert names == ["api", "worker", "migrator"], (
        f"container definitions moved or were renamed: {names}; "
        "update this reader rather than loosening it"
    )
    i = names.index(name)
    end = starts[i + 1][1] if i + 1 < len(starts) else len(tf)
    return tf[starts[i][1] : end]


class TestTerraformWiring:
    def test_api_container_sets_the_variable_settings_reads(self):
        from config import Settings

        tf = _ECS_MODULE.read_text()
        env_name = "shake_report_ring".upper()
        assert "shake_report_ring" in Settings.model_fields
        entry = re.compile(
            r'\{\s*name\s*=\s*"' + env_name + r'"\s*,\s*value\s*=\s*var\.shake_report_ring\s*\}'
        )
        assert entry.search(_container_block(tf, "api")), (
            f"{env_name} is not in the API container's environment — the "
            "ring would serve its default forever"
        )
        # Only the API serves the flag; the worker reading it would be a
        # second source of truth.
        assert not entry.search(_container_block(tf, "worker"))

    def test_terraform_validation_accepts_exactly_the_settings_values(self):
        from config import ShakeReportRing

        tf = _ECS_MODULE.read_text()
        var = re.search(r'variable "shake_report_ring" \{(.*?)\n\}', tf, re.S)
        assert var, 'variable "shake_report_ring" missing from the ECS module'
        body = var.group(1)
        default = re.search(r'default\s*=\s*"([^"]*)"', body)
        assert default and default.group(1) == "admins"
        allowed = re.search(r"contains\(\[([^\]]*)\],\s*var\.shake_report_ring\)", body)
        assert allowed, "the variable has no contains([...]) validation"
        tf_values = set(re.findall(r'"([^"]*)"', allowed.group(1)))
        assert tf_values == set(get_args(ShakeReportRing)) == set(_RINGS)

    def test_prod_passes_a_valid_ring_explicitly(self):
        """The switch is a line in prod's module call, not a module
        default someone has to know about. Its value is Leo's to change,
        so only its validity is asserted."""
        prod = _PROD_ENV.read_text()
        ecs_call = re.search(r'module "ecs" \{(.*?)\n\}', prod, re.S)
        assert ecs_call
        ring = re.findall(r'^\s*shake_report_ring\s*=\s*"([^"]*)"', ecs_call.group(1), re.M)
        assert len(ring) == 1 and ring[0] in _RINGS, ring


# ---------------------------------------------------------------------------
# Feedback: context.trigger
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    from api.v1.user.create_user_feedback import _reset_rate_limit_for_test

    _reset_rate_limit_for_test()
    yield
    _reset_rate_limit_for_test()


@pytest.fixture
def mock_send_task():
    with patch("api.v1.user.create_user_feedback.celery_app.send_task") as m:
        yield m


def _feedback_rows(mock_async_db):
    added = [c.args[0] for c in mock_async_db.db.add.call_args_list]
    return [r for r in added if type(r).__name__ == "UserFeedback"]


class TestFeedbackTrigger:
    @pytest.mark.parametrize("trigger", ["shake", "profile"])
    def test_valid_trigger_is_stored(
        self, client, mock_user, mock_async_db, mock_send_task, trigger,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={
                "body": "The timer froze",
                "context": {
                    "app_version": "1.0.40",
                    "platform": "android",
                    "route": "/recipes/abc",
                    "trigger": trigger,
                },
            },
        )
        assert response.status_code == 201, response.text
        rows = _feedback_rows(mock_async_db)
        assert len(rows) == 1
        assert rows[0].context == {
            "app_version": "1.0.40",
            "platform": "android",
            "route": "/recipes/abc",
            "trigger": trigger,
        }

    def test_absent_trigger_stores_none(
        self, client, mock_user, mock_async_db, mock_send_task,
    ):
        """Clients released before shk102 send no trigger; they keep
        working and their rows carry no `trigger` key at all."""
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi", "context": {"route": "/profile"}},
        )
        assert response.status_code == 201, response.text
        rows = _feedback_rows(mock_async_db)
        assert len(rows) == 1
        assert rows[0].context == {"route": "/profile"}
        assert "trigger" not in rows[0].context

    def test_unknown_trigger_is_422_and_writes_no_row(
        self, client, mock_user, mock_async_db, mock_send_task,
    ):
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi", "context": {"trigger": "wiggle"}},
        )
        assert response.status_code == 422
        # The 422 must be the trigger's VALUE being refused, not the key.
        # Before shk101 `trigger` was an unknown key, so this request was
        # already a 422 — `extra_forbidden` — and a status-only check
        # passed on code that accepted no trigger at all.
        errors = response.json()["detail"]
        assert [(e["type"], e["loc"]) for e in errors] == [
            ("literal_error", ["body", "context", "trigger"]),
        ], errors
        assert _feedback_rows(mock_async_db) == []
        mock_async_db.db.commit.assert_not_called()
        mock_send_task.assert_not_called()

    def test_feedback_id_round_trips(
        self, client, mock_user, mock_async_db, mock_send_task,
    ):
        """A trigger does not change the response shape the sheet reads."""
        response = client.post(
            "/v1/users/me/feedback",
            json={"body": "Hi", "context": {"trigger": "shake"}},
        )
        assert response.status_code == 201
        assert uuid.UUID(response.json()["id"])
        assert response.json()["status"] == "unread"
