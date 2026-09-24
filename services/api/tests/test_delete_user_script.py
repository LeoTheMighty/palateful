"""Tests for services/api/scripts/delete_user.py.

Same shape as `test_promote_admin_script.py`: load the script as a module
and mock the connection, so no live DB is needed.

The tests worth reading are the refusals. This script's failure mode is
not "it errors" — it is "it deletes the wrong thing, or half of the right
thing", and neither announces itself.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT_PATH = (
    pathlib.Path(__file__).parent.parent / "scripts" / "delete_user.py"
)

QA_ID = "061fe939-49a0-41aa-9f3f-000000000000"
QA_EMAIL = "qa@example.test"

# (table, column, delete_rule) — the real prod shape, trimmed:
# measured 2026-09-24 as 44 FKs, CASCADE 27 / SET NULL 16 / NO ACTION 1.
FKS = [
    ("calendars", "owner_id", "CASCADE"),
    ("calendar_users", "user_id", "CASCADE"),
    ("client_latencies", "user_id", "SET NULL"),
    ("ingredients", "submitted_by_id", "NO ACTION"),
]


@pytest.fixture(scope="module")
def delete_user():
    spec = importlib.util.spec_from_file_location("delete_user", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["delete_user"] = module
    spec.loader.exec_module(module)
    return module


def _user(**overrides: Any) -> dict[str, Any]:
    base = {
        "id": QA_ID,
        "email": QA_EMAIL,
        "name": "QA",
        "auth0_id": "auth0|qa",
        "is_admin": False,
        "created_at": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def run_script(delete_user):
    """Run `main(argv)` against a stubbed DB; returns (exit_code, executed)."""

    def _run(
        argv: list[str],
        user: dict[str, Any] | None = None,
        fks: list[tuple[str, str, str]] | None = None,
        counts: dict[tuple[str, str], int] | None = None,
        reappears: bool = False,
    ):
        user = _user() if user is None else user
        fks = FKS if fks is None else fks
        counts = counts or {}
        executed: list[str] = []

        conn = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.begin.return_value.__enter__ = MagicMock(return_value=None)
        conn.begin.return_value.__exit__ = MagicMock(return_value=False)

        def execute(stmt, params=None):
            sql = " ".join(str(stmt).split())
            executed.append(sql)
            result = MagicMock()
            if sql.startswith("SELECT id, email"):
                row = MagicMock()
                row._mapping = user
                result.__iter__ = lambda self: iter([row] if user else [])
                return result
            if "information_schema" in sql:
                result.__iter__ = lambda self: iter(fks)
                return result
            if sql.startswith("SELECT count(*) FROM users WHERE auth0_id"):
                result.scalar_one.return_value = 1 if reappears else 0
                return result
            if sql.startswith("SELECT count(*)"):
                table = sql.split('FROM "')[1].split('"')[0]
                column = sql.split('WHERE "')[1].split('"')[0]
                result.scalar_one.return_value = counts.get((table, column), 0)
                return result
            return result

        conn.execute.side_effect = execute
        engine = MagicMock()
        engine.connect.return_value = conn

        with patch.object(delete_user, "_get_engine", return_value=engine), \
             patch.object(delete_user, "time") as fake_time:
            fake_time.sleep.return_value = None
            code = delete_user.main(argv)
        return code, executed

    return _run


# --- resolution -------------------------------------------------------------


def test_dry_run_is_the_default_and_writes_nothing(run_script, capsys):
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL],
        counts={("calendars", "owner_id"): 1, ("client_latencies", "user_id"): 761},
    )
    assert code == 0
    assert not [s for s in executed if s.startswith(("DELETE", "UPDATE", "INSERT"))]
    out = capsys.readouterr().out
    assert "REMOVED" in out and "KEPT, UNATTRIBUTED" in out
    assert "761" in out, "per-table counts must be printed, not a summary"


def test_no_match_exits_2(run_script):
    code, _ = run_script(["--id-or-email", "nobody@example.test"], user={})
    assert code == 2


# --- the guards -------------------------------------------------------------


def test_admin_is_refused_outright(run_script, capsys):
    """No override exists on purpose — see the module docstring."""
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes"],
        user=_user(is_admin=True),
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "admin" in capsys.readouterr().err.lower()


def test_mismatched_confirm_email_refuses(run_script, capsys):
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", "qa@exmaple.test",
         "--auth0-disabled", "--yes"],
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "--confirm-email" in capsys.readouterr().err


def test_missing_auth0_attestation_refuses(run_script, capsys):
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL, "--yes"],
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "--auth0-disabled" in capsys.readouterr().err


def test_user_without_an_email_cannot_be_confirmed(run_script, capsys):
    code, executed = run_script(
        ["--id-or-email", QA_ID, "--confirm-email", "", "--auth0-disabled",
         "--yes"],
        user=_user(email=None),
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]


def test_an_unknown_blocking_fk_stops_the_run(run_script, capsys):
    """Schema drift must fail closed, not delete half the graph."""
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes"],
        fks=[*FKS, ("audit_trail", "actor_id", "RESTRICT")],
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    err = capsys.readouterr().err
    assert "audit_trail.actor_id" in err


# --- the delete itself ------------------------------------------------------


def test_commit_clears_the_by_name_fk_before_deleting(run_script):
    """`ingredients.submitted_by_id` has no ondelete — measured, prod.

    A plain DELETE errors partway through when the user submitted
    ingredients, leaving the graph half-removed. It must be nulled first,
    and the ordering matters: null, then delete.
    """
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes", "--verify-after", "0"],
        counts={("ingredients", "submitted_by_id"): 3},
    )
    assert code == 0
    null_ix = next(
        i for i, s in enumerate(executed)
        if s.startswith('UPDATE "ingredients" SET "submitted_by_id" = NULL')
    )
    delete_ix = next(
        i for i, s in enumerate(executed) if s.startswith("DELETE FROM users")
    )
    assert null_ix < delete_ix, "the blocking FK must be cleared first"


def test_commit_clears_the_user_self_references(run_script, delete_user):
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes", "--verify-after", "0"],
    )
    assert code == 0
    for column in delete_user.USER_SELF_REFERENCES:
        assert any(
            s.startswith(f'UPDATE users SET "{column}" = NULL')
            for s in executed
        )


def test_commit_writes_an_audit_row(run_script):
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes", "--verify-after", "0"],
    )
    assert code == 0
    audit = [s for s in executed if s.startswith("INSERT INTO error_logs")]
    assert len(audit) == 1
    assert "'audit'" in audit[0] and "UserDeletionAudit" in audit[0]


def test_error_logs_are_reported_but_never_touched(run_script, capsys):
    """They have no FK, so nothing nulls them; they must survive visibly."""
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes", "--verify-after", "0"],
        counts={("error_logs", "user_id"): 6},
    )
    assert code == 0
    assert not [
        s for s in executed
        if s.startswith('UPDATE "error_logs"') or s.startswith("DELETE FROM error_logs")
    ]
    assert "NO FK" in capsys.readouterr().out


# --- the self-undo ----------------------------------------------------------


def test_a_reappearing_user_is_reported_as_failure(run_script, capsys):
    """The whole point of the post-commit check.

    A live Auth0 identity means the next authed request recreates the
    user. Without this, the script reports success over a deletion that
    undid itself seconds later.
    """
    code, _ = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes"],
        reappears=True,
    )
    assert code == 1
    assert "reappeared" in capsys.readouterr().err


def test_verify_can_be_disabled(run_script, capsys):
    code, _ = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL,
         "--auth0-disabled", "--yes", "--verify-after", "0"],
        reappears=True,
    )
    assert code == 0, "--verify-after 0 skips the check entirely"
