"""Tests for POST /v1/client-latencies (cla-1b).

Covers:
- 100-event cap + 413 overflow
- Authed path: user_id derived from JWT, body-supplied user_id ignored
- Anonymous path: user_id=null, IP rate-limit (10 events/min)
- Server-side route redaction (422 on un-redacted segments)
- Empty batch → 200 accepted=0 (no DB write)
- Pydantic validation (unknown type / platform / negative duration)
- Model constants stay in sync with the Pydantic Literal enums

aam-21: handler is now `AsyncEndpoint` — fixtures override the async
optional-auth dep (`get_optional_user_async`) and assertions run against
`mock_async_db.db.execute` (which replaces the sync
`bulk_insert_mappings` call with `insert(ClientLatency).values(rows)`).
"""

from __future__ import annotations

import pytest

import api.v1.client_latency.ingest as ingest_module
from api.v1.client_latency.ingest import (
    ClientLatencyPlatform,
    ClientLatencyType,
    MAX_EVENTS_PER_REQUEST,
    _reset_anon_rate_limit_for_test,
)
from utils.models.client_latency import (
    CLIENT_LATENCY_PLATFORMS,
    CLIENT_LATENCY_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    _reset_anon_rate_limit_for_test()
    yield
    _reset_anon_rate_limit_for_test()


def _insert_call_rows(execute_mock):
    """Extract the rows list passed to the most recent `await db.execute(insert(...), rows)` call.

    The handler uses `await self.db.execute(insert(ClientLatency), rows)`
    — so the second positional arg is the row dicts list. This helper
    isolates the "what rows landed?" question so test asserts stay
    readable.
    """
    call = execute_mock.call_args
    assert call is not None, "db.execute was not called"
    return call.args[1]


@pytest.fixture
def authed_client(mock_db, mock_async_db, mock_user):
    """TestClient where get_optional_user_async returns the mock user.

    aam-21: sync deps still overridden so a stray sync handler doesn't
    crash during the dual-dispatch window.
    """
    from dependencies import (
        get_async_database,
        get_database,
        get_optional_user,
        get_optional_user_async,
    )
    from main import app
    from fastapi.testclient import TestClient

    def override_get_database():
        return mock_db

    async def override_get_async_database():
        yield mock_async_db

    async def override_get_optional_user():
        return mock_user

    async def override_get_optional_user_async():
        return mock_user

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_async_database] = override_get_async_database
    app.dependency_overrides[get_optional_user] = override_get_optional_user
    app.dependency_overrides[get_optional_user_async] = (
        override_get_optional_user_async
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(mock_db, mock_async_db):
    """TestClient with NO auth override — optional auth resolves to None."""
    from dependencies import get_async_database, get_database
    from main import app
    from fastapi.testclient import TestClient

    def override_get_database():
        return mock_db

    async def override_get_async_database():
        yield mock_async_db

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[get_async_database] = override_get_async_database

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _event(**overrides):
    """Build a minimal valid event body."""
    defaults = {
        "type": "route_paint",
        "platform": "ios",
        "app_version": "1.0.53",
        "duration_ms": 120,
        "route": "/home",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Event cap + 413
# ---------------------------------------------------------------------------


class TestEventCap:
    def test_accepts_at_cap(self, authed_client, mock_async_db):
        events = [_event() for _ in range(MAX_EVENTS_PER_REQUEST)]
        response = authed_client.post(
            "/v1/client-latencies", json={"events": events}
        )
        assert response.status_code == 200
        assert response.json()["accepted"] == MAX_EVENTS_PER_REQUEST
        mock_async_db.db.execute.assert_called_once()

    def test_over_cap_returns_413(self, authed_client, mock_async_db):
        events = [_event() for _ in range(MAX_EVENTS_PER_REQUEST + 1)]
        response = authed_client.post(
            "/v1/client-latencies", json={"events": events}
        )
        assert response.status_code == 413
        body = response.json()
        assert body["data"]["max_events"] == MAX_EVENTS_PER_REQUEST
        mock_async_db.db.execute.assert_not_called()

    def test_empty_batch_is_a_noop(self, authed_client, mock_async_db):
        response = authed_client.post(
            "/v1/client-latencies", json={"events": []}
        )
        assert response.status_code == 200
        assert response.json()["accepted"] == 0
        mock_async_db.db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Authed path — user_id derived from JWT
# ---------------------------------------------------------------------------


class TestAuthedPath:
    def test_user_id_derived_from_current_user(
        self, authed_client, mock_async_db, mock_user
    ):
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [_event()]},
        )
        assert response.status_code == 200
        assert response.json()["accepted"] == 1
        rows = _insert_call_rows(mock_async_db.db.execute)
        assert rows[0]["user_id"] == mock_user.id

    def test_body_user_id_is_ignored(self, authed_client):
        """Extra keys on events are forbidden — a body-supplied user_id
        must be rejected at validation time so we can't silently ingest
        a spoofed id."""
        event = _event()
        event["user_id"] = "11111111-1111-1111-1111-111111111111"
        response = authed_client.post(
            "/v1/client-latencies", json={"events": [event]}
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Anonymous path — user_id=null + IP rate-limit
# ---------------------------------------------------------------------------


class TestAnonymousPath:
    def test_anon_insert_persists_null_user_id(
        self, anon_client, mock_async_db
    ):
        response = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event()]},
        )
        assert response.status_code == 200
        rows = _insert_call_rows(mock_async_db.db.execute)
        assert rows[0]["user_id"] is None

    def test_anon_over_rate_limit_returns_429(self, anon_client):
        # 10 events in one batch exhausts the window; an 11th event
        # in the next batch must be rejected.
        first = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event() for _ in range(10)]},
        )
        assert first.status_code == 200

        second = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event()]},
        )
        assert second.status_code == 429
        assert "retry_after_s" in second.json()["data"]

    def test_anon_batch_would_exceed_window_rejected_atomically(
        self, anon_client, mock_async_db
    ):
        """A single batch > 10 events from an anonymous caller is
        rejected outright — the rate-limit counts events, not requests,
        so we can't let half the batch through."""
        events = [_event() for _ in range(11)]
        response = anon_client.post(
            "/v1/client-latencies", json={"events": events}
        )
        assert response.status_code == 429
        mock_async_db.db.execute.assert_not_called()

    def test_anon_empty_batch_does_not_consume_quota(self, anon_client):
        """Empty batches are a successful no-op and must not eat quota
        — a misbehaving client that probes with empty bodies still
        has its real events go through."""
        for _ in range(5):
            response = anon_client.post(
                "/v1/client-latencies", json={"events": []}
            )
            assert response.status_code == 200

        # We should still have full quota for 10 real events.
        response = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event() for _ in range(10)]},
        )
        assert response.status_code == 200

    def test_rate_limit_keys_on_forwarded_ip_when_present(
        self, anon_client
    ):
        """`X-Forwarded-For` (ALB/CloudFront) wins over direct
        client host. Different XFF values → independent buckets."""
        headers_a = {"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}
        headers_b = {"X-Forwarded-For": "5.6.7.8, 10.0.0.1"}

        r1 = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event() for _ in range(10)]},
            headers=headers_a,
        )
        assert r1.status_code == 200

        # Same IP → rate-limited.
        r2 = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event()]},
            headers=headers_a,
        )
        assert r2.status_code == 429

        # Different IP → full quota.
        r3 = anon_client.post(
            "/v1/client-latencies",
            json={"events": [_event()]},
            headers=headers_b,
        )
        assert r3.status_code == 200


# ---------------------------------------------------------------------------
# Redaction guard
# ---------------------------------------------------------------------------


class TestRouteRedactionGuard:
    @pytest.mark.parametrize(
        "route",
        [
            "/recipes/abcd1234-ef56-7890-abcd-ef1234567890/edit",
            "/users/123456/profile",
            "/recipes/deadbeef-dead-beef-dead-beefdeadbeef",
        ],
    )
    def test_unredacted_route_returns_422(
        self, authed_client, mock_async_db, route
    ):
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [_event(route=route)]},
        )
        assert response.status_code == 422
        mock_async_db.db.execute.assert_not_called()

    @pytest.mark.parametrize(
        "route",
        [
            "/home",
            "/recipes",
            "/recipes/:id/edit",
            "/recipes/{id}/edit",
            "/books/view",
            "/v1",  # short numeric not flagged
            None,
        ],
    )
    def test_redacted_or_none_route_passes(
        self, authed_client, mock_async_db, route
    ):
        payload = _event()
        if route is None:
            payload.pop("route", None)
        else:
            payload["route"] = route
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [payload]},
        )
        assert response.status_code == 200

    def test_422_on_first_bad_event_short_circuits(
        self, authed_client, mock_async_db
    ):
        """Mixed batch with one raw UUID rejects the whole batch — the
        async bulk insert can't do partial writes."""
        events = [
            _event(route="/home"),
            _event(route="/recipes/abcd1234-ef56-7890-abcd-ef1234567890"),
            _event(route="/books"),
        ]
        response = authed_client.post(
            "/v1/client-latencies", json={"events": events}
        )
        assert response.status_code == 422
        assert response.json()["data"]["index"] == 1
        mock_async_db.db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_unknown_type_rejected(self, authed_client):
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [_event(type="not_a_real_type")]},
        )
        assert response.status_code == 422

    def test_unknown_platform_rejected(self, authed_client):
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [_event(platform="linux")]},
        )
        assert response.status_code == 422

    def test_negative_duration_rejected(self, authed_client):
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [_event(duration_ms=-5)]},
        )
        assert response.status_code == 422

    def test_silly_large_duration_rejected(self, authed_client):
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [_event(duration_ms=60 * 60 * 1000)]},  # 1h
        )
        assert response.status_code == 422

    def test_missing_app_version_rejected(self, authed_client):
        payload = _event()
        payload.pop("app_version")
        response = authed_client.post(
            "/v1/client-latencies",
            json={"events": [payload]},
        )
        assert response.status_code == 422

    def test_empty_string_optional_fields_normalize_to_null(
        self, authed_client, mock_async_db
    ):
        """Blank-string route/endpoint/metric_name/device_class from the
        client collapse to NULL so we don't carry empty-string noise
        into the column (and don't trip the redaction guard on `""`)."""
        response = authed_client.post(
            "/v1/client-latencies",
            json={
                "events": [
                    _event(
                        route="",
                        endpoint="   ",
                        metric_name="",
                        device_class="",
                    )
                ]
            },
        )
        assert response.status_code == 200
        rows = _insert_call_rows(mock_async_db.db.execute)
        assert rows[0]["route"] is None
        assert rows[0]["endpoint"] is None
        assert rows[0]["metric_name"] is None
        assert rows[0]["device_class"] is None

    def test_extra_bag_is_stored_verbatim(
        self, authed_client, mock_async_db
    ):
        response = authed_client.post(
            "/v1/client-latencies",
            json={
                "events": [
                    _event(
                        type="metrickit_daily",
                        extra={"launch_time_ms": 1800, "hangs_s": 2.1},
                    )
                ]
            },
        )
        assert response.status_code == 200
        rows = _insert_call_rows(mock_async_db.db.execute)
        assert rows[0]["extra"] == {
            "launch_time_ms": 1800,
            "hangs_s": 2.1,
        }


# ---------------------------------------------------------------------------
# Constant drift guard
# ---------------------------------------------------------------------------


def test_literal_enums_match_model_constants():
    """`ingest.py` re-declares the Literal values (Pydantic can't read
    them from a tuple directly). Pin equality so a new event type can't
    be added to the model without updating both."""
    import typing

    type_args = typing.get_args(ClientLatencyType)
    platform_args = typing.get_args(ClientLatencyPlatform)
    assert type_args == CLIENT_LATENCY_TYPES
    assert platform_args == CLIENT_LATENCY_PLATFORMS


# ---------------------------------------------------------------------------
# Client-IP fallback path
# ---------------------------------------------------------------------------


class TestClientIpFallback:
    def test_missing_request_uses_unknown_bucket(self):
        """Direct call into `_extract_client_ip` without a request
        object yields the `unknown` bucket — confirms the helper
        doesn't NPE on a missing request and rate-limits still apply."""
        assert ingest_module._extract_client_ip(None) == "unknown"

    def test_no_xff_and_no_client_host(self):
        class _Req:
            headers: dict = {}
            client = None

        assert ingest_module._extract_client_ip(_Req()) == "unknown"

    def test_direct_client_host(self):
        class _Client:
            host = "203.0.113.5"

        class _Req:
            headers: dict = {}
            client = _Client()

        assert ingest_module._extract_client_ip(_Req()) == "203.0.113.5"

    def test_empty_xff_falls_back_to_client_host(self):
        class _Client:
            host = "203.0.113.5"

        class _Req:
            headers = {"X-Forwarded-For": ""}
            client = _Client()

        assert ingest_module._extract_client_ip(_Req()) == "203.0.113.5"
