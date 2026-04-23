"""Tests for the client-latency admin endpoints (cla-10a).

Covers:
- GET /v1/admin/metrics/client/routes
- GET /v1/admin/metrics/client/endpoints
- GET /v1/admin/metrics/client/jank
- GET /v1/admin/metrics/client/sparkline

Query shape is asserted via the `mock_db.db.execute` call args — we
don't stand up a real Postgres. Router-level filters + 100% branch
coverage assertions live here.
"""

from __future__ import annotations

from types import SimpleNamespace

from conftest import MockExecuteResult


# ---------------------------------------------------------------------------
# Tiny SimpleNamespace helpers for row fakes
# ---------------------------------------------------------------------------


def _route_row(**kw):
    defaults = {
        "route": "/home",
        "p50": 100,
        "p95": 500,
        "p99": 1000,
        "total": 42,
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _endpoint_row(**kw):
    defaults = {
        "method": "GET",
        "endpoint": "/v1/recipe-books",
        "p50": 20,
        "p95": 80,
        "p99": 200,
        "total": 77,
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _jank_row(**kw):
    defaults = {
        "route": "/home",
        "build_p95": 8,
        "raster_p95": 5,
        "total": 60,
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _sparkline_row(**kw):
    defaults = {"bucket_idx": 0, "bucket_mean": 150.0}
    defaults.update(kw)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/routes
# ---------------------------------------------------------------------------


class TestGetClientRouteMetrics:
    def test_returns_rows(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _route_row(route="/recipes/:id", p50=120, p95=900, p99=1500, total=50),
        ])
        resp = client.get("/v1/admin/metrics/client/routes?window=24h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["window"] == "24h"
        assert data["rows"][0]["route"] == "/recipes/:id"
        assert data["rows"][0]["p95_ms"] == 900
        assert data["rows"][0]["count"] == 50

    def test_null_p95_tolerated(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _route_row(p50=None, p95=None, p99=None, total=0),
        ])
        resp = client.get("/v1/admin/metrics/client/routes")
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["p50_ms"] == 0
        assert row["p95_ms"] == 0
        assert row["count"] == 0

    def test_empty(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/admin/metrics/client/routes?window=7d")
        assert resp.status_code == 200
        assert resp.json()["rows"] == []

    def test_invalid_window(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        resp = client.get("/v1/admin/metrics/client/routes?window=365d")
        assert resp.status_code == 400

    def test_accepts_all_four_windows(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        for window in ("1h", "24h", "7d", "30d"):
            mock_db.db.execute.return_value = MockExecuteResult([])
            resp = client.get(f"/v1/admin/metrics/client/routes?window={window}")
            assert resp.status_code == 200
            assert resp.json()["window"] == window

    def test_filters_propagate_to_sql_params(
        self, client, mock_user, mock_db
    ):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get(
            "/v1/admin/metrics/client/routes"
            "?window=1h&platform=ios&app_version=1.2.3&route=/home"
        )
        assert resp.status_code == 200
        params = _last_execute_args_dict(mock_db)
        assert params.get("platform") == "ios", params
        assert params.get("app_version") == "1.2.3"
        assert params.get("route") == "/home"

    def test_non_admin_gets_403(self, client, mock_user, mock_db):
        mock_user.is_admin = False
        resp = client.get("/v1/admin/metrics/client/routes")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/endpoints
# ---------------------------------------------------------------------------


class TestGetClientEndpointMetrics:
    def test_returns_rows(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _endpoint_row(),
        ])
        resp = client.get("/v1/admin/metrics/client/endpoints")
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        assert rows[0]["method"] == "GET"
        assert rows[0]["endpoint"] == "/v1/recipe-books"

    def test_invalid_window_rejected(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        resp = client.get("/v1/admin/metrics/client/endpoints?window=bogus")
        assert resp.status_code == 400

    def test_empty(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/admin/metrics/client/endpoints?window=24h")
        assert resp.status_code == 200
        assert resp.json()["rows"] == []

    def test_null_method_coerced_to_empty_string(
        self, client, mock_user, mock_db
    ):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _endpoint_row(method=None),
        ])
        resp = client.get("/v1/admin/metrics/client/endpoints")
        assert resp.status_code == 200
        assert resp.json()["rows"][0]["method"] == ""


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/jank
# ---------------------------------------------------------------------------


class TestGetClientJankMetrics:
    def test_returns_rows(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _jank_row(route="/home", build_p95=9, raster_p95=6, total=61),
        ])
        resp = client.get("/v1/admin/metrics/client/jank?window=7d")
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["build_p95_ms"] == 9
        assert row["raster_p95_ms"] == 6
        assert row["count"] == 61

    def test_invalid_window(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        resp = client.get("/v1/admin/metrics/client/jank?window=bad")
        assert resp.status_code == 400

    def test_empty(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/admin/metrics/client/jank")
        assert resp.status_code == 200
        assert resp.json()["rows"] == []

    def test_null_percentiles(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _jank_row(build_p95=None, raster_p95=None),
        ])
        resp = client.get("/v1/admin/metrics/client/jank")
        assert resp.status_code == 200
        row = resp.json()["rows"][0]
        assert row["build_p95_ms"] == 0
        assert row["raster_p95_ms"] == 0


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/client/sparkline
# ---------------------------------------------------------------------------


class TestGetClientSparkline:
    def test_returns_24_buckets(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _sparkline_row(bucket_idx=0, bucket_mean=100.0),
            _sparkline_row(bucket_idx=23, bucket_mean=200.0),
        ])
        resp = client.get(
            "/v1/admin/metrics/client/sparkline"
            "?metric=route_paint&window=24h&route=/home"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "route_paint"
        assert data["window"] == "24h"
        assert len(data["buckets"]) == 24
        assert data["buckets"][0] == 100.0
        assert data["buckets"][23] == 200.0
        assert data["buckets"][10] == 0.0

    def test_invalid_metric(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        resp = client.get(
            "/v1/admin/metrics/client/sparkline?metric=not_a_thing&window=24h"
        )
        assert resp.status_code == 400

    def test_invalid_window(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        resp = client.get(
            "/v1/admin/metrics/client/sparkline?metric=app_start&window=nope"
        )
        assert resp.status_code == 400

    def test_all_filter_combinations(self, client, mock_user, mock_db):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get(
            "/v1/admin/metrics/client/sparkline"
            "?metric=network_request&window=1h&platform=android"
            "&app_version=1.0.0&endpoint=/v1/recipes/:id"
        )
        assert resp.status_code == 200
        params = _last_execute_args_dict(mock_db)
        assert params["metric"] == "network_request"
        assert params["platform"] == "android"
        assert params["app_version"] == "1.0.0"
        assert params["endpoint"] == "/v1/recipes/:id"

    def test_null_bucket_mean_coerced_to_zero(
        self, client, mock_user, mock_db
    ):
        mock_user.is_admin = True
        mock_db.db.execute.return_value = MockExecuteResult([
            _sparkline_row(bucket_idx=5, bucket_mean=None),
        ])
        resp = client.get(
            "/v1/admin/metrics/client/sparkline?metric=app_start"
        )
        assert resp.status_code == 200
        assert resp.json()["buckets"][5] == 0.0


# ---------------------------------------------------------------------------
# tiny helpers
# ---------------------------------------------------------------------------


def _last_execute_call(mock_db):
    return mock_db.db.execute.call_args


def _last_execute_args_dict(mock_db):
    args, _ = mock_db.db.execute.call_args
    # Endpoints call db.execute(text(sql), params) → args[1] is the
    # params dict.
    return args[1]
