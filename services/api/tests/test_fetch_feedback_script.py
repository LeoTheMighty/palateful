"""Tests for services/api/scripts/fetch_feedback.py.

The script hits the DB via raw SQLAlchemy and streams rows to stdout. We
import the module and exercise the public surface (`main`, `_build_query`,
`_resolve_since`) with a mock engine/connection so these tests don't need
a live DB.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import sys
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT_PATH = (
    pathlib.Path(__file__).parent.parent / "scripts" / "fetch_feedback.py"
)


@pytest.fixture(scope="module")
def fetch_feedback():
    spec = importlib.util.spec_from_file_location(
        "fetch_feedback", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fetch_feedback"] = module
    spec.loader.exec_module(module)
    return module


def _row(**over):
    base = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "user_email": "author@example.com",
        "user_name": "Jane Doe",
        "body": "Share sheet bounces me to home",
        "category": "bug",
        "status": "unread",
        "context": {"app_version": "1.0.13", "platform": "ios"},
        "created_at": datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC),
    }
    base.update(over)
    return SimpleNamespace(_mapping=base)


def _fake_conn(rows: list):
    """Build a connection that returns `rows` on .execute()."""
    conn = MagicMock()

    def execute(query, params=None):
        result = MagicMock()
        result.__iter__.return_value = iter(rows)
        return result

    options_mock = MagicMock()
    options_mock.execute.side_effect = execute
    conn.execution_options.return_value = options_mock
    conn.execute.side_effect = execute
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    return conn


def _fake_engine(conn):
    engine = MagicMock()
    engine.connect.return_value = conn

    # begin() used for audit write — make it a silent context manager
    begin_cm = MagicMock()
    begin_cm.__enter__ = MagicMock(return_value=MagicMock(execute=MagicMock()))
    begin_cm.__exit__ = MagicMock(return_value=False)
    engine.begin.return_value = begin_cm
    return engine


# ---------------------------------------------------------------------------
# --help / --since / --status / --format parsing
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_defaults(self, fetch_feedback):
        args = fetch_feedback._parse_args([])
        assert args.since == "7d"
        assert args.status == "unread"
        assert args.format == "csv"

    def test_explicit_all(self, fetch_feedback):
        args = fetch_feedback._parse_args(
            ["--since", "all", "--status", "all", "--format", "json"]
        )
        assert args.since == "all"
        assert args.status == "all"
        assert args.format == "json"

    def test_invalid_status_rejected(self, fetch_feedback):
        with pytest.raises(SystemExit):
            fetch_feedback._parse_args(["--status", "spam"])

    def test_invalid_format_rejected(self, fetch_feedback):
        with pytest.raises(SystemExit):
            fetch_feedback._parse_args(["--format", "xml"])


class TestResolveSince:
    def test_returns_none_for_all(self, fetch_feedback):
        assert fetch_feedback._resolve_since("all") is None

    def test_7d(self, fetch_feedback):
        cutoff = fetch_feedback._resolve_since("7d")
        assert cutoff is not None
        # Sanity: 7 days is between 6 and 8 days in the past
        from datetime import datetime as dt
        from datetime import timedelta as td
        now = dt.now(UTC)
        assert now - td(days=8) < cutoff < now - td(days=6)

    def test_invalid_since_exits_1(self, fetch_feedback):
        with pytest.raises(SystemExit) as exc:
            fetch_feedback._resolve_since("yesterday")
        assert exc.value.code == 1


class TestBuildQuery:
    def test_default_filter(self, fetch_feedback):
        sql, params = fetch_feedback._build_query(
            status="unread",
            cutoff=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert "f.status = :status" in sql
        assert "f.created_at >= :cutoff" in sql
        assert "ORDER BY f.created_at DESC" in sql
        assert params["status"] == "unread"

    def test_status_all_drops_status_filter(self, fetch_feedback):
        sql, params = fetch_feedback._build_query(
            status="all",
            cutoff=datetime(2026, 4, 1, tzinfo=UTC),
        )
        assert "f.status = :status" not in sql
        assert "status" not in params

    def test_since_all_drops_cutoff_filter(self, fetch_feedback):
        sql, params = fetch_feedback._build_query(status="unread", cutoff=None)
        assert "f.created_at >= :cutoff" not in sql
        assert "cutoff" not in params

    def test_since_all_status_all_has_no_where_clause(self, fetch_feedback):
        sql, params = fetch_feedback._build_query(status="all", cutoff=None)
        assert " WHERE " not in sql
        assert params == {}


# ---------------------------------------------------------------------------
# Output formats (CSV / TSV / JSON-lines)
# ---------------------------------------------------------------------------


class TestOutputFormats:
    def test_csv_has_header_and_row(self, fetch_feedback, capsys):
        rows = [_row(body="Hello, world")]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            code = fetch_feedback.main(
                ["--since", "7d", "--status", "unread", "--format", "csv"]
            )
        assert code == 0
        out = capsys.readouterr().out
        lines = out.strip().splitlines()
        assert lines[0].startswith(
            "id,user_id,user_email,user_name,body,category,status,"
        )
        # Header + 1 data row
        assert len(lines) == 2
        # CSV quoted the comma in the body
        assert '"Hello, world"' in lines[1]

    def test_tsv_uses_tab_separator(self, fetch_feedback, capsys):
        rows = [_row()]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            code = fetch_feedback.main(["--format", "tsv"])
        assert code == 0
        out = capsys.readouterr().out
        lines = out.strip().splitlines()
        assert "\t" in lines[0]

    def test_json_is_jsonlines(self, fetch_feedback, capsys):
        rows = [_row(), _row(body="Second")]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            code = fetch_feedback.main(["--format", "json"])
        assert code == 0
        out = capsys.readouterr().out
        lines = [ln for ln in out.strip().splitlines() if ln]
        assert len(lines) == 2
        # Every line is standalone JSON
        for line in lines:
            parsed = json.loads(line)
            assert "id" in parsed
            assert "body" in parsed

    def test_json_preserves_context_as_object(self, fetch_feedback, capsys):
        rows = [_row(context={"app_version": "1.0.13", "platform": "ios"})]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            fetch_feedback.main(["--format", "json"])
        out = capsys.readouterr().out
        parsed = json.loads(out.strip().splitlines()[0])
        assert parsed["context"] == {
            "app_version": "1.0.13", "platform": "ios",
        }

    def test_csv_serializes_context_as_json_string(
        self, fetch_feedback, capsys,
    ):
        rows = [_row(context={"app_version": "1.0.13"})]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            fetch_feedback.main(["--format", "csv"])
        out = capsys.readouterr().out
        # Context cell has the JSON dict encoded as a string
        assert '"{""app_version"": ""1.0.13""}"' in out or \
            '{"app_version": "1.0.13"}' in out

    def test_null_cells_serialize_to_empty_string_in_csv(
        self, fetch_feedback, capsys,
    ):
        rows = [_row(category=None, context=None, user_email=None, user_name=None)]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            fetch_feedback.main(["--format", "csv"])
        out = capsys.readouterr().out
        # Count trailing commas / empties in data line
        data_line = out.strip().splitlines()[1]
        # Empty category slot (preceded and followed by a comma)
        assert ",," in data_line


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_zero_rows_exits_2(self, fetch_feedback, capsys):
        conn = _fake_conn([])
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            code = fetch_feedback.main(["--since", "7d"])
        assert code == 2
        err = capsys.readouterr().err
        assert "no feedback rows matched" in err

    def test_db_error_exits_1(self, fetch_feedback, capsys):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.__exit__.return_value = False
        conn.execution_options.side_effect = RuntimeError("DB down")
        conn.execute.side_effect = RuntimeError("DB down")
        engine = _fake_engine(conn)
        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            code = fetch_feedback.main([])
        assert code == 1

    def test_missing_database_url_exits_1(
        self, fetch_feedback, monkeypatch, capsys,
    ):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(SystemExit) as exc:
            fetch_feedback._get_engine()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "DATABASE_URL is not set" in err


# ---------------------------------------------------------------------------
# Audit row
# ---------------------------------------------------------------------------


class TestAuditRow:
    def test_audit_row_written_on_success(self, fetch_feedback):
        rows = [_row(), _row()]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)

        captured = {}
        begin_conn = MagicMock()

        def execute_capture(sql, params):
            captured["sql"] = str(sql)
            captured["params"] = params
            return MagicMock()

        begin_conn.execute.side_effect = execute_capture
        engine.begin.return_value.__enter__ = MagicMock(return_value=begin_conn)
        engine.begin.return_value.__exit__ = MagicMock(return_value=False)

        with (
            patch.object(fetch_feedback, "_get_engine", return_value=engine),
            # Silence stdout via a StringIO redirect so CSV doesn't pollute
            # pytest's output
            patch.object(sys, "stdout", new=io.StringIO()),
        ):
            fetch_feedback.main(["--format", "csv"])

        assert "INSERT INTO error_logs" in captured["sql"]
        assert captured["params"]["etype"] == "FeedbackExport"
        assert "rows=2" in captured["params"]["emsg"]
        assert 'by script:fetch_feedback' in captured["params"]["emsg"]
        assert captured["params"]["svc"] == "audit"

    def test_audit_failure_is_non_fatal(self, fetch_feedback, capsys):
        rows = [_row()]
        conn = _fake_conn(rows)
        engine = _fake_engine(conn)
        engine.begin.side_effect = RuntimeError("audit write rejected")

        with patch.object(fetch_feedback, "_get_engine", return_value=engine):
            code = fetch_feedback.main([])
        assert code == 0  # success despite audit failure
        err = capsys.readouterr().err
        assert "failed to write audit row" in err
