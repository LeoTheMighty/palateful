"""Tests for services/api/scripts/analyze_latency.py.

Mirrors test_fetch_feedback_script.py. The script hits the DB via raw
SQLAlchemy; we import it and exercise `main`, the query-builders, and
the output coercion/emission helpers with a mocked engine/connection so
no live DB is required. A microbenchmark test exercises the full
`main()` path against a 1000-row mocked result set to confirm the
script's aggregation/format cost is bounded.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT_PATH = (
    pathlib.Path(__file__).parent.parent / "scripts" / "analyze_latency.py"
)


@pytest.fixture(scope="module")
def analyze_latency():
    spec = importlib.util.spec_from_file_location(
        "analyze_latency", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_latency"] = module
    spec.loader.exec_module(module)
    return module


def _endpoint_row(**over):
    base = {
        "method": "GET",
        "normalized_path": "/v1/recipes",
        "count": 42,
        "p50_ms": 120.0,
        "p95_ms": 450.0,
        "p99_ms": 900.0,
        "max_ms": 1200,
    }
    base.update(over)
    return SimpleNamespace(_mapping=base)


def _task_row(**over):
    base = {
        "task_name": "extract_recipe_task",
        "status": "success",
        "count": 17,
        "p50_ms": 5000.0,
        "p95_ms": 15000.0,
        "p99_ms": 20000.0,
        "max_ms": 25000,
    }
    base.update(over)
    return SimpleNamespace(_mapping=base)


def _regression_row(**over):
    base = {
        "method": "GET",
        "normalized_path": "/v1/meals",
        "baseline_p95_ms": 200.0,
        "recent_p95_ms": 500.0,
        "pct_increase": 150.0,
        "recent_count": 57,
    }
    base.update(over)
    return SimpleNamespace(_mapping=base)


def _client_row(**over):
    base = {
        "type": "route_paint",
        "platform": "ios",
        "route": "/home",
        "count": 60,
        "p50_ms": 120.0,
        "p95_ms": 450.0,
        "p99_ms": 900.0,
        "max_ms": 1500,
    }
    base.update(over)
    return SimpleNamespace(_mapping=base)


def _client_regression_row(**over):
    base = {
        "type": "route_paint",
        "platform": "ios",
        "route": "/home",
        "baseline_p95_ms": 200.0,
        "recent_p95_ms": 500.0,
        "pct_increase": 150.0,
        "recent_count": 60,
    }
    base.update(over)
    return SimpleNamespace(_mapping=base)


def _fake_conn(rows_by_query):
    """`rows_by_query` is a list of lists; one list per execute() call,
    delivered in order. Simulates the endpoint + task two-query pattern."""
    conn = MagicMock()
    queue = list(rows_by_query)

    def execute(query, params=None):
        result = MagicMock()
        next_rows = queue.pop(0) if queue else []
        result.__iter__.return_value = iter(next_rows)
        return result

    conn.execute.side_effect = execute
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    return conn


def _fake_engine(conn):
    engine = MagicMock()
    engine.connect.return_value = conn
    return engine


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_defaults(self, analyze_latency):
        args = analyze_latency._parse_args([])
        assert args.window == "24h"
        assert args.top == 15
        assert args.format == "table"
        assert args.regression_hunt is False
        assert args.min_samples == 5
        assert args.client_min_samples == 50
        assert args.section == "both"

    def test_explicit_csv_regression_hunt(self, analyze_latency):
        args = analyze_latency._parse_args(
            [
                "--window", "7d",
                "--top", "25",
                "--format", "csv",
                "--regression-hunt",
                "--min-samples", "0",
                "--section", "endpoints",
            ]
        )
        assert args.window == "7d"
        assert args.top == 25
        assert args.format == "csv"
        assert args.regression_hunt is True
        assert args.min_samples == 0
        assert args.section == "endpoints"

    def test_invalid_window_rejected(self, analyze_latency):
        with pytest.raises(SystemExit):
            analyze_latency._parse_args(["--window", "forever"])

    def test_invalid_format_rejected(self, analyze_latency):
        with pytest.raises(SystemExit):
            analyze_latency._parse_args(["--format", "xml"])

    def test_invalid_section_rejected(self, analyze_latency):
        with pytest.raises(SystemExit):
            analyze_latency._parse_args(["--section", "neither"])


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------


class TestClampTop:
    def test_clamp_minimum(self, analyze_latency):
        assert analyze_latency._clamp_top(0) == 1
        assert analyze_latency._clamp_top(-5) == 1

    def test_clamp_maximum(self, analyze_latency):
        assert analyze_latency._clamp_top(101) == 100
        assert analyze_latency._clamp_top(9999) == 100

    def test_pass_through(self, analyze_latency):
        assert analyze_latency._clamp_top(15) == 15


# ---------------------------------------------------------------------------
# Query builders (SQL surface)
# ---------------------------------------------------------------------------


class TestBuildEndpointQuery:
    def test_24h_window(self, analyze_latency):
        sql = analyze_latency._build_endpoint_query("24h", 15, 5)
        assert "FROM request_latencies" in sql
        assert "created_at >= NOW() - INTERVAL '24 hours'" in sql
        assert "HAVING COUNT(*) >= 5" in sql
        assert "ORDER BY p95_ms DESC" in sql
        assert "LIMIT 15" in sql

    def test_all_window_drops_created_at_clause(self, analyze_latency):
        sql = analyze_latency._build_endpoint_query("all", 15, 5)
        assert "created_at" not in sql

    def test_min_samples_zero_drops_having(self, analyze_latency):
        sql = analyze_latency._build_endpoint_query("7d", 15, 0)
        assert "HAVING" not in sql

    def test_1h_7d_windows_translate(self, analyze_latency):
        sql_1h = analyze_latency._build_endpoint_query("1h", 15, 5)
        sql_7d = analyze_latency._build_endpoint_query("7d", 15, 5)
        assert "INTERVAL '1 hour'" in sql_1h
        assert "INTERVAL '7 days'" in sql_7d


class TestBuildTaskQuery:
    def test_contains_task_latencies(self, analyze_latency):
        sql = analyze_latency._build_task_query("24h", 15, 5)
        assert "FROM task_latencies" in sql
        assert "GROUP BY task_name, status" in sql

    def test_all_window_drops_created_at_clause(self, analyze_latency):
        sql = analyze_latency._build_task_query("all", 15, 0)
        assert "created_at" not in sql


class TestBuildRegressionQuery:
    def test_cte_shape(self, analyze_latency):
        sql = analyze_latency._build_regression_query(15)
        assert "WITH recent AS" in sql
        assert "baseline AS" in sql
        assert "NOW() - INTERVAL '24 hours'" in sql
        assert "NOW() - INTERVAL '30 days'" in sql
        assert "NOW() - INTERVAL '7 days'" in sql
        assert "recent.cnt >= 10" in sql
        assert "recent.p95 > baseline.p95 * 1.5" in sql
        assert "ORDER BY pct_increase DESC" in sql


class TestBuildClientQuery:
    def test_contains_client_latencies_and_grouping(self, analyze_latency):
        sql = analyze_latency._build_client_query("24h", 15, 50)
        assert "FROM client_latencies" in sql
        assert "GROUP BY type, platform, route" in sql
        assert "HAVING COUNT(*) >= 50" in sql
        assert "ORDER BY p95_ms DESC" in sql

    def test_min_samples_zero_drops_having(self, analyze_latency):
        sql = analyze_latency._build_client_query("24h", 15, 0)
        assert "HAVING" not in sql

    def test_all_window_drops_created_at(self, analyze_latency):
        sql = analyze_latency._build_client_query("all", 15, 50)
        assert "created_at" not in sql


class TestBuildClientRegressionQuery:
    def test_cte_shape_and_2x_threshold(self, analyze_latency):
        sql = analyze_latency._build_client_regression_query(15, 50)
        assert "WITH recent AS" in sql
        assert "FROM client_latencies" in sql
        assert "NOW() - INTERVAL '24 hours'" in sql
        assert "NOW() - INTERVAL '30 days'" in sql
        assert "NOW() - INTERVAL '7 days'" in sql
        # Client threshold is 2.0x, not server's 1.5x — this is the
        # single most important invariant of this story (ptd-6 AC2).
        assert "recent.p95 > baseline.p95 * 2.0" in sql
        # Client-side min-samples is a queryable threshold, not a
        # post-hoc HAVING; check it's applied in the CTE filter.
        assert "recent.cnt >= 50" in sql
        assert "ORDER BY pct_increase DESC" in sql

    def test_min_samples_override(self, analyze_latency):
        sql = analyze_latency._build_client_regression_query(15, 10)
        assert "recent.cnt >= 10" in sql


# ---------------------------------------------------------------------------
# Row coercion
# ---------------------------------------------------------------------------


class TestCoerceEndpointRow:
    def test_basic(self, analyze_latency):
        out = analyze_latency._coerce_endpoint_row(
            {
                "method": "GET",
                "normalized_path": "/v1/recipes",
                "count": 10,
                "p50_ms": 100.567,
                "p95_ms": 400.0,
                "p99_ms": 800.0,
                "max_ms": 999,
            }
        )
        assert out["section"] == "endpoints"
        assert out["count"] == 10
        # rounds to 1 decimal
        assert out["p50_ms"] == 100.6

    def test_handles_none(self, analyze_latency):
        out = analyze_latency._coerce_endpoint_row({
            "method": None,
            "normalized_path": None,
            "count": None,
            "p50_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "max_ms": None,
        })
        assert out["count"] == 0
        assert out["p50_ms"] is None


class TestCoerceTaskRow:
    def test_basic(self, analyze_latency):
        out = analyze_latency._coerce_task_row(
            {
                "task_name": "foo",
                "status": "success",
                "count": 1,
                "p50_ms": 1.0,
                "p95_ms": 2.0,
                "p99_ms": 3.0,
                "max_ms": 4,
            }
        )
        assert out["section"] == "tasks"
        assert out["task_name"] == "foo"


class TestCoerceRegressionRow:
    def test_basic(self, analyze_latency):
        out = analyze_latency._coerce_regression_row(
            {
                "method": "GET",
                "normalized_path": "/v1/meals",
                "baseline_p95_ms": 200.0,
                "recent_p95_ms": 500.0,
                "pct_increase": 150.0,
                "recent_count": 55,
            }
        )
        assert out["section"] == "regression"
        assert out["pct_increase"] == 150.0
        assert out["recent_count"] == 55


class TestCoerceClientRow:
    def test_basic(self, analyze_latency):
        out = analyze_latency._coerce_client_row(_client_row()._mapping)
        assert out["section"] == "client"
        assert out["type"] == "route_paint"
        assert out["platform"] == "ios"
        assert out["route"] == "/home"
        assert out["count"] == 60

    def test_null_route_preserved(self, analyze_latency):
        out = analyze_latency._coerce_client_row(
            _client_row(route=None)._mapping
        )
        # app_start / MetricKit daily events have no route. We keep it
        # None rather than coercing to "-", so JSON consumers can tell
        # the difference between "missing" and a literal "-" route.
        assert out["route"] is None


class TestCoerceClientRegressionRow:
    def test_basic(self, analyze_latency):
        out = analyze_latency._coerce_client_regression_row(
            _client_regression_row()._mapping
        )
        assert out["section"] == "client_regression"
        assert out["type"] == "route_paint"
        assert out["pct_increase"] == 150.0
        assert out["recent_count"] == 60


# ---------------------------------------------------------------------------
# Output formats
# ---------------------------------------------------------------------------


class TestEmitCsv:
    def test_both_sections(self, analyze_latency, capsys):
        endpoints = [
            analyze_latency._coerce_endpoint_row(_endpoint_row()._mapping),
        ]
        tasks = [
            analyze_latency._coerce_task_row(_task_row()._mapping),
        ]
        total = analyze_latency._emit(
            "csv", endpoints=endpoints, tasks=tasks, regression=None,
        )
        assert total == 2
        out = capsys.readouterr().out
        # Endpoint header
        assert "section,method,normalized_path,count,p50_ms,p95_ms,p99_ms,max_ms" in out
        # Task header
        assert "section,task_name,status,count,p50_ms,p95_ms,p99_ms,max_ms" in out
        # Data rows
        assert "endpoints,GET,/v1/recipes" in out
        assert "tasks,extract_recipe_task,success" in out


class TestEmitJson:
    def test_jsonlines_per_section(self, analyze_latency, capsys):
        endpoints = [analyze_latency._coerce_endpoint_row(_endpoint_row()._mapping)]
        tasks = [analyze_latency._coerce_task_row(_task_row()._mapping)]
        total = analyze_latency._emit(
            "json", endpoints=endpoints, tasks=tasks, regression=None,
        )
        assert total == 2
        lines = [
            ln for ln in capsys.readouterr().out.strip().splitlines() if ln
        ]
        assert len(lines) == 2
        for ln in lines:
            parsed = json.loads(ln)
            assert "section" in parsed
            assert parsed["section"] in ("endpoints", "tasks")


class TestEmitTable:
    def test_headers_and_row(self, analyze_latency, capsys):
        endpoints = [analyze_latency._coerce_endpoint_row(_endpoint_row()._mapping)]
        tasks = [analyze_latency._coerce_task_row(_task_row()._mapping)]
        total = analyze_latency._emit(
            "table", endpoints=endpoints, tasks=tasks, regression=None,
        )
        assert total == 2
        out = capsys.readouterr().out
        assert "endpoints (top by p95 desc)" in out
        assert "tasks (top by p95 desc)" in out
        assert "/v1/recipes" in out
        assert "extract_recipe_task" in out

    def test_empty_sections_print_hint(self, analyze_latency, capsys):
        total = analyze_latency._emit(
            "table", endpoints=[], tasks=[], regression=None,
        )
        assert total == 0
        out = capsys.readouterr().out
        assert "no endpoint samples matched the filter" in out
        assert "no task samples matched the filter" in out

    def test_regression_block(self, analyze_latency, capsys):
        regression = [
            analyze_latency._coerce_regression_row(_regression_row()._mapping),
        ]
        total = analyze_latency._emit(
            "table", endpoints=None, tasks=None, regression=regression,
        )
        assert total == 1
        out = capsys.readouterr().out
        assert "regression_hunt" in out
        assert "/v1/meals" in out


# ---------------------------------------------------------------------------
# main() — end-to-end with mocked engine
# ---------------------------------------------------------------------------


class TestMainEndToEnd:
    def test_default_invocation_both_sections(self, analyze_latency, capsys):
        conn = _fake_conn([[_endpoint_row()], [_task_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main([])
        assert code == 0
        out = capsys.readouterr().out
        assert "endpoints" in out
        assert "tasks" in out

    def test_endpoints_only_section(self, analyze_latency, capsys):
        conn = _fake_conn([[_endpoint_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--section", "endpoints"])
        assert code == 0
        # engine.connect().execute should have been called once (endpoints only)
        assert conn.execute.call_count == 1

    def test_tasks_only_section(self, analyze_latency):
        conn = _fake_conn([[_task_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--section", "tasks"])
        assert code == 0
        assert conn.execute.call_count == 1

    def test_regression_hunt_single_query(self, analyze_latency, capsys):
        conn = _fake_conn([[_regression_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--regression-hunt", "--format", "csv"])
        assert code == 0
        # Regression implies endpoints-only — one query
        assert conn.execute.call_count == 1
        out = capsys.readouterr().out
        assert "baseline_p95_ms,recent_p95_ms" in out

    def test_empty_result_exits_2(self, analyze_latency, capsys):
        conn = _fake_conn([[], []])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main([])
        assert code == 2
        err = capsys.readouterr().err
        assert "no latency samples matched" in err

    def test_db_error_exits_1(self, analyze_latency, capsys):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        conn.execute.side_effect = RuntimeError("DB down")
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main([])
        assert code == 1

    def test_missing_database_url_exits_1(
        self, analyze_latency, monkeypatch, capsys,
    ):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(SystemExit) as exc:
            analyze_latency._get_engine()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "DATABASE_URL is not set" in err

    def test_csv_format_has_section_column(self, analyze_latency, capsys):
        conn = _fake_conn([[_endpoint_row()], [_task_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--format", "csv"])
        assert code == 0
        out = capsys.readouterr().out
        lines = out.strip().splitlines()
        assert lines[0].startswith("section,")
        # Both sections emit their own header
        assert any(ln.startswith("section,task_name") for ln in lines)

    def test_json_format_is_ndjson(self, analyze_latency, capsys):
        conn = _fake_conn([[_endpoint_row()], [_task_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--format", "json"])
        assert code == 0
        lines = capsys.readouterr().out.strip().splitlines()
        # One line per row
        assert len(lines) == 2
        for ln in lines:
            json.loads(ln)


class TestClientSectionEndToEnd:
    """End-to-end coverage for the ptd-6 additions.

    Pins which queries fire for each --section value, and confirms the
    two regression-hunt flows (server-only vs combined all) emit
    distinct tables without leaking each other's columns.
    """

    def test_section_client_fires_only_client_query(self, analyze_latency, capsys):
        conn = _fake_conn([[_client_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--section", "client"])
        assert code == 0
        assert conn.execute.call_count == 1
        out = capsys.readouterr().out
        assert "client (top by p95 desc)" in out
        assert "/home" in out
        # Endpoint/task headers must NOT leak.
        assert "endpoints (top by p95 desc)" not in out
        assert "tasks (top by p95 desc)" not in out

    def test_section_all_fires_three_queries(self, analyze_latency, capsys):
        conn = _fake_conn([[_endpoint_row()], [_task_row()], [_client_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--section", "all"])
        assert code == 0
        assert conn.execute.call_count == 3
        out = capsys.readouterr().out
        assert "endpoints (top by p95 desc)" in out
        assert "tasks (top by p95 desc)" in out
        assert "client (top by p95 desc)" in out

    def test_section_both_remains_backward_compatible(
        self, analyze_latency, capsys,
    ):
        # 'both' was the pre-ptd-6 default — it must still run exactly
        # two queries (endpoints + tasks) and not touch client_latencies.
        conn = _fake_conn([[_endpoint_row()], [_task_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(["--section", "both"])
        assert code == 0
        assert conn.execute.call_count == 2
        out = capsys.readouterr().out
        assert "client (top by p95 desc)" not in out

    def test_regression_hunt_client_only(self, analyze_latency, capsys):
        conn = _fake_conn([[_client_regression_row()]])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(
                ["--regression-hunt", "--section", "client"]
            )
        assert code == 0
        assert conn.execute.call_count == 1
        out = capsys.readouterr().out
        assert "client_regression_hunt" in out
        assert "2.0x" in out
        # Server regression block must not appear.
        assert "regression_hunt (recent 24h p95 > 1.5x" not in out

    def test_regression_hunt_all_fires_server_and_client(
        self, analyze_latency, capsys,
    ):
        conn = _fake_conn([
            [_regression_row()],
            [_client_regression_row()],
        ])
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            code = analyze_latency.main(
                ["--regression-hunt", "--section", "all"]
            )
        assert code == 0
        assert conn.execute.call_count == 2
        out = capsys.readouterr().out
        assert "regression_hunt (recent 24h p95 > 1.5x" in out
        assert "client_regression_hunt" in out

    def test_client_min_samples_flag_overrides(self, analyze_latency):
        captured_sqls: list[str] = []

        def execute(query, params=None):
            captured_sqls.append(str(query))
            result = MagicMock()
            result.__iter__.return_value = iter([])
            return result

        conn = MagicMock()
        conn.execute.side_effect = execute
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            analyze_latency.main([
                "--section", "client",
                "--client-min-samples", "7",
            ])
        assert any("HAVING COUNT(*) >= 7" in sql for sql in captured_sqls)

    def test_regression_hunt_client_min_samples_override(
        self, analyze_latency,
    ):
        captured_sqls: list[str] = []

        def execute(query, params=None):
            captured_sqls.append(str(query))
            result = MagicMock()
            result.__iter__.return_value = iter([])
            return result

        conn = MagicMock()
        conn.execute.side_effect = execute
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        engine = _fake_engine(conn)
        with patch.object(analyze_latency, "_get_engine", return_value=engine):
            analyze_latency.main([
                "--regression-hunt", "--section", "client",
                "--client-min-samples", "3",
            ])
        assert any(
            "recent.cnt >= 3" in sql and "client_latencies" in sql
            for sql in captured_sqls
        )


# ---------------------------------------------------------------------------
# Microbenchmark — asserts aggregation/formatting is cheap
# ---------------------------------------------------------------------------


class TestMicrobenchmark:
    def test_1000_rows_runs_fast(self, analyze_latency):
        """Script formatting/coercion path stays under 1s even at 1000 rows.

        Real 1M-row stress is a Postgres-side cost; what we measure here
        is the Python-side hot loop. If we regress a 50x slowdown, the
        test catches it.
        """
        endpoint_rows = [
            _endpoint_row(normalized_path=f"/v1/fake/{i}", p95_ms=50.0 + i)
            for i in range(1000)
        ]
        task_rows = [
            _task_row(task_name=f"task_{i}", p95_ms=100.0 + i)
            for i in range(1000)
        ]
        conn = _fake_conn([endpoint_rows, task_rows])
        engine = _fake_engine(conn)
        start = time.monotonic()
        with (
            patch.object(analyze_latency, "_get_engine", return_value=engine),
            # swallow stdout so we don't spam the test log
            patch.object(sys, "stdout", new=io.StringIO()),
        ):
            code = analyze_latency.main(["--top", "100", "--format", "csv"])
        elapsed = time.monotonic() - start
        assert code == 0
        assert elapsed < 1.0, f"script body took {elapsed:.3f}s on 2k rows"
