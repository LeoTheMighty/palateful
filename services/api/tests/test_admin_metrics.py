"""Tests for GetEndpointMetrics, GetTaskMetrics, and the
GetStats latency extension (obs-latency-2).

Uses the standard `mock_async_db` fixture — we don't spin up real Postgres
here; we assert on the shape of the query results and the endpoint's
merging logic.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from conftest import MockExecuteResult


# ---------------------------------------------------------------------------
# Helpers — simulate SQL row objects returned by db.execute().all() / first()
# ---------------------------------------------------------------------------


def _percentile_row(**kwargs):
    defaults = {
        "method": "GET",
        "normalized_path": "/v1/recipes",
        "p50": 100,
        "p95": 500,
        "p99": 900,
        "total": 10,
        "errors": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _task_percentile_row(**kwargs):
    defaults = {
        "task_name": "import.parse_url",
        "p50": 100,
        "p95": 500,
        "p99": 900,
        "total": 10,
        "failures": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _sparkline_row(**kwargs):
    defaults = {
        "method": "GET",
        "normalized_path": "/v1/recipes",
        "bucket_idx": 0,
        "bucket_mean": 100.0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _task_sparkline_row(**kwargs):
    defaults = {"task_name": "import.parse_url", "bucket_idx": 0, "bucket_mean": 100.0}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/endpoints
# ---------------------------------------------------------------------------


class TestGetEndpointMetrics:
    def test_returns_rows_with_sparklines(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(
                [
                    _percentile_row(
                        method="GET",
                        normalized_path="/v1/recipes/{recipe_id}",
                        p50=120,
                        p95=2100,
                        p99=3000,
                        total=50,
                        errors=1,
                    ),
                ]
            ),
            MockExecuteResult(
                [
                    _sparkline_row(
                        method="GET",
                        normalized_path="/v1/recipes/{recipe_id}",
                        bucket_idx=3,
                        bucket_mean=50.0,
                    ),
                    _sparkline_row(
                        method="GET",
                        normalized_path="/v1/recipes/{recipe_id}",
                        bucket_idx=23,
                        bucket_mean=2100.0,
                    ),
                ]
            ),
        ]

        response = client.get("/v1/admin/metrics/endpoints?window=24h")
        assert response.status_code == 200
        data = response.json()
        assert data["window"] == "24h"
        assert len(data["rows"]) == 1
        row = data["rows"][0]
        assert row["method"] == "GET"
        assert row["normalized_path"] == "/v1/recipes/{recipe_id}"
        assert row["p95_ms"] == 2100
        assert row["count"] == 50
        assert row["error_rate"] == pytest.approx(1 / 50)
        assert len(row["sparkline"]) == 24
        assert row["sparkline"][3] == 50.0
        assert row["sparkline"][23] == 2100.0
        # Empty buckets default to 0.0
        assert row["sparkline"][0] == 0.0

    def test_empty_dataset_returns_empty_rows(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),
            MockExecuteResult([]),
        ]
        response = client.get("/v1/admin/metrics/endpoints?window=24h")
        assert response.status_code == 200
        data = response.json()
        assert data["rows"] == []

    def test_invalid_window_rejected(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        response = client.get("/v1/admin/metrics/endpoints?window=30d")
        assert response.status_code == 400

    def test_default_window_is_24h(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),
            MockExecuteResult([]),
        ]
        response = client.get("/v1/admin/metrics/endpoints")
        assert response.status_code == 200
        assert response.json()["window"] == "24h"

    def test_accepts_all_three_windows(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        for window in ("1h", "24h", "7d"):
            mock_async_db.db.execute.side_effect = [
                MockExecuteResult([]),
                MockExecuteResult([]),
            ]
            response = client.get(f"/v1/admin/metrics/endpoints?window={window}")
            assert response.status_code == 200
            assert response.json()["window"] == window


# ---------------------------------------------------------------------------
# GET /v1/admin/metrics/tasks
# ---------------------------------------------------------------------------


class TestGetTaskMetrics:
    def test_returns_rows_with_failure_rate(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(
                [
                    _task_percentile_row(
                        task_name="worker.import.ocr_extract",
                        p50=40000,
                        p95=60000,
                        p99=90000,
                        total=100,
                        failures=12,
                    ),
                ]
            ),
            MockExecuteResult(
                [
                    _task_sparkline_row(
                        task_name="worker.import.ocr_extract",
                        bucket_idx=5,
                        bucket_mean=55000.0,
                    ),
                ]
            ),
        ]

        response = client.get("/v1/admin/metrics/tasks?window=24h")
        assert response.status_code == 200
        rows = response.json()["rows"]
        assert len(rows) == 1
        assert rows[0]["task_name"] == "worker.import.ocr_extract"
        assert rows[0]["p95_ms"] == 60000
        assert rows[0]["failure_rate"] == pytest.approx(12 / 100)
        assert rows[0]["sparkline"][5] == 55000.0

    def test_multiple_sparkline_rows_per_task_merge(
        self, client, mock_user, mock_async_db
    ):
        """Two buckets for the same task populate distinct indices on one sparkline."""
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(
                [_task_percentile_row(task_name="t.one", total=4, failures=0)]
            ),
            MockExecuteResult(
                [
                    _task_sparkline_row(task_name="t.one", bucket_idx=2, bucket_mean=10.0),
                    _task_sparkline_row(task_name="t.one", bucket_idx=5, bucket_mean=25.0),
                ]
            ),
        ]
        response = client.get("/v1/admin/metrics/tasks?window=24h")
        assert response.status_code == 200
        sparkline = response.json()["rows"][0]["sparkline"]
        assert sparkline[2] == 10.0
        assert sparkline[5] == 25.0

    def test_empty_tasks_returns_empty(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),
            MockExecuteResult([]),
        ]
        response = client.get("/v1/admin/metrics/tasks?window=1h")
        assert response.status_code == 200
        assert response.json() == {"window": "1h", "rows": []}

    def test_invalid_window_rejected(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        response = client.get("/v1/admin/metrics/tasks?window=forever")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v1/admin/stats — obs-latency-2 extension
# ---------------------------------------------------------------------------


class TestGetStatsLatencyExtension:
    def test_overall_p95_and_slowest_endpoint_returned(
        self, client, mock_user, mock_async_db
    ):
        mock_user.is_admin = True
        # Mirrors the query order in get_stats.py:
        # 1) total_users, 2) total_recipes, 3) total_recipe_books,
        # 4) errors_24h, 5) active_users_7d, 6) unread_feedback,
        # 7) overall_p95_ms, 8) slowest_endpoint
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([5]),  # total_users
            MockExecuteResult([12]),  # total_recipes
            MockExecuteResult([3]),  # total_recipe_books
            MockExecuteResult([0]),  # errors_24h
            MockExecuteResult([4]),  # active_users_7d
            MockExecuteResult([1]),  # unread_feedback
            MockExecuteResult([320]),  # overall_p95_ms
            MockExecuteResult(
                [
                    SimpleNamespace(
                        method="GET",
                        normalized_path="/v1/recipes",
                        p95_ms=2100,
                    )
                ]
            ),
        ]

        response = client.get("/v1/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_p95_ms"] == 320
        assert data["slowest_endpoint"]["method"] == "GET"
        assert data["slowest_endpoint"]["normalized_path"] == "/v1/recipes"
        assert data["slowest_endpoint"]["p95_ms"] == 2100

    def test_cold_start_returns_nulls(self, client, mock_user, mock_async_db):
        mock_user.is_admin = True
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([0]),  # total_users
            MockExecuteResult([0]),  # total_recipes
            MockExecuteResult([0]),  # total_recipe_books
            MockExecuteResult([0]),  # errors_24h
            MockExecuteResult([0]),  # active_users_7d
            MockExecuteResult([0]),  # unread_feedback
            MockExecuteResult([None]),  # overall_p95_ms (no samples)
            MockExecuteResult([]),  # slowest_endpoint (no rows)
        ]
        response = client.get("/v1/admin/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_p95_ms"] is None
        assert data["slowest_endpoint"] is None
