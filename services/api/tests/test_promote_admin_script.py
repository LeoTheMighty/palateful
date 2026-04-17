"""Tests for services/api/scripts/promote_admin.py.

The script talks to the database via SQLAlchemy but is otherwise pure
stdlib. We import its functions directly and mock out the engine/
connection so these tests don't need a live DB.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import UTC
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Load the script as a module even though it lives outside the src tree.
_SCRIPT_PATH = (
    pathlib.Path(__file__).parent.parent / "scripts" / "promote_admin.py"
)


@pytest.fixture(scope="module")
def promote_admin():
    spec = importlib.util.spec_from_file_location(
        "promote_admin", _SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["promote_admin"] = module
    spec.loader.exec_module(module)
    return module


def _fake_conn_with_matches(matches: list[dict]):
    """Build a MagicMock context-managed connection returning `matches`.

    Accepts any number of SELECT/UPDATE/INSERT calls. Only the first
    .execute() is expected to be a SELECT whose rows are `matches`.
    """
    conn = MagicMock()

    def execute(query, params=None):
        # Naive: any SELECT returns the seeded matches, UPDATE/INSERT no-ops.
        sql = str(query)
        result = MagicMock()
        if "SELECT" in sql.upper():
            result.__iter__.return_value = iter(
                [SimpleNamespace(_mapping=m) for m in matches]
            )
        else:
            result.__iter__.return_value = iter([])
        return result

    conn.execute.side_effect = execute
    conn.begin.return_value.__enter__ = MagicMock(return_value=None)
    conn.begin.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    return conn


def _fake_engine(conn) -> MagicMock:
    engine = MagicMock()
    engine.connect.return_value = conn
    return engine


def test_parse_args_defaults_to_promote(promote_admin):
    args = promote_admin._parse_args(["--email", "x@y.com"])
    assert args.email == "x@y.com"
    assert args.action == "promote"
    assert args.yes is False


def test_parse_args_demote(promote_admin):
    args = promote_admin._parse_args(["--email", "x@y.com", "--demote"])
    assert args.action == "demote"


def test_parse_args_yes_flag(promote_admin):
    args = promote_admin._parse_args(["--email", "x@y.com", "--yes"])
    assert args.yes is True


def test_no_user_matches_returns_code_2(promote_admin, capsys):
    conn = _fake_conn_with_matches([])
    engine = _fake_engine(conn)
    with patch.object(promote_admin, "_get_engine", return_value=engine):
        code = promote_admin.main(["--email", "ghost@x.com", "--yes"])
    assert code == 2
    err = capsys.readouterr().err
    assert "no user with email" in err


def test_multiple_users_match_returns_code_2(promote_admin, capsys):
    import uuid
    from datetime import datetime

    now = datetime.now(UTC)
    matches = [
        {
            "id": uuid.uuid4(),
            "email": "dup@x.com",
            "name": "A",
            "created_at": now,
            "is_admin": False,
        },
        {
            "id": uuid.uuid4(),
            "email": "dup@x.com",
            "name": "B",
            "created_at": now,
            "is_admin": False,
        },
    ]
    conn = _fake_conn_with_matches(matches)
    engine = _fake_engine(conn)
    with patch.object(promote_admin, "_get_engine", return_value=engine):
        code = promote_admin.main(["--email", "dup@x.com", "--yes"])
    assert code == 2
    err = capsys.readouterr().err
    assert "2 users matched" in err


def test_dry_run_prints_but_does_not_write(promote_admin, capsys):
    import uuid
    from datetime import datetime

    now = datetime.now(UTC)
    matches = [
        {
            "id": uuid.uuid4(),
            "email": "leo@x.com",
            "name": "Leo",
            "created_at": now,
            "is_admin": False,
        },
    ]
    conn = _fake_conn_with_matches(matches)
    engine = _fake_engine(conn)
    with patch.object(promote_admin, "_get_engine", return_value=engine):
        code = promote_admin.main(["--email", "leo@x.com"])
    assert code == 0
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "Re-run with --yes" in out


def test_noop_when_already_in_target_state(promote_admin, capsys):
    import uuid
    from datetime import datetime

    now = datetime.now(UTC)
    matches = [
        {
            "id": uuid.uuid4(),
            "email": "leo@x.com",
            "name": "Leo",
            "created_at": now,
            "is_admin": True,
        },
    ]
    conn = _fake_conn_with_matches(matches)
    engine = _fake_engine(conn)
    with patch.object(promote_admin, "_get_engine", return_value=engine):
        # promote when already admin → no-op
        code = promote_admin.main(["--email", "leo@x.com", "--yes"])
    assert code == 0
    out = capsys.readouterr().out
    assert "NO-OP" in out
    assert "already admin" in out


def test_yes_commits_and_prints_grep_line(promote_admin, capsys):
    import uuid
    from datetime import datetime

    now = datetime.now(UTC)
    matches = [
        {
            "id": uuid.uuid4(),
            "email": "leo@x.com",
            "name": "Leo",
            "created_at": now,
            "is_admin": False,
        },
    ]
    conn = _fake_conn_with_matches(matches)
    engine = _fake_engine(conn)
    with patch.object(promote_admin, "_get_engine", return_value=engine):
        code = promote_admin.main(["--email", "leo@x.com", "--yes"])
    assert code == 0
    out = capsys.readouterr().out
    # Grep-able log line present
    assert "PROMOTE_ADMIN" in out
    assert "actor=script:promote_admin" in out
    assert "before=False" in out
    assert "after=True" in out
