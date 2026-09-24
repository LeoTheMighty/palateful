"""Tests for services/api/scripts/qa_cleanup.py.

This script is intended to hold a **standing** permission grant, so the
tests that matter are the ones proving it cannot reach outside its scope
no matter what ids it is handed. A guard that only works when the
operator is careful is not what the grant rests on.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_SCRIPT_PATH = (
    pathlib.Path(__file__).parent.parent / "scripts" / "qa_cleanup.py"
)
_INGREDIENT_MODEL = (
    pathlib.Path(__file__).parents[3]
    / "libraries" / "utils" / "utils" / "models" / "ingredient.py"
)

QA_ID = "061fe939-49a0-41aa-9f3f-000000000000"
QA_EMAIL = "qa@example.test"
BOOK_ID = "b0000000-0000-0000-0000-000000000001"
RECIPE_ID = "11111111-1111-1111-1111-111111111111"
INGREDIENT_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="module")
def qa_cleanup():
    spec = importlib.util.spec_from_file_location("qa_cleanup", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["qa_cleanup"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run_script(qa_cleanup):
    """Run `main(argv)` against a stubbed DB. Returns (code, executed)."""

    def _run(
        argv: list[str],
        user: dict[str, Any] | None = None,
        owner_rows: int = 1,
        other_members: int = 0,
        refs_before: int = 0,
        refs_after: int = 0,
        recipe_exists: bool = True,
    ):
        user = user if user is not None else {
            "id": QA_ID, "email": QA_EMAIL, "name": "QA", "is_admin": False
        }
        executed: list[str] = []
        state = {"deleted_recipe": False}

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
            if sql.startswith("SELECT recipe_book_id"):
                result.scalar.return_value = BOOK_ID if recipe_exists else None
                return result
            if "role = 'owner'" in sql:
                result.scalar_one.return_value = owner_rows
                return result
            if "user_id <> :u" in sql:
                result.scalar_one.return_value = other_members
                return result
            if sql.startswith("SELECT count(*) FROM \"recipe_ingredients\""):
                # references drop once the owning recipe is deleted
                result.scalar_one.return_value = (
                    refs_after if state["deleted_recipe"] else refs_before
                )
                return result
            if sql.startswith("SELECT count(*)"):
                result.scalar_one.return_value = 0
                return result
            if sql.startswith("DELETE FROM recipes"):
                state["deleted_recipe"] = True
            return result

        conn.execute.side_effect = execute
        engine = MagicMock()
        engine.connect.return_value = conn
        with patch.object(qa_cleanup, "_get_engine", return_value=engine):
            try:
                code = qa_cleanup.main(argv)
            except SystemExit as exc:  # rollback path raises
                code = int(exc.code or 0)
        return code, executed

    return _run


BASE = ["--id-or-email", QA_EMAIL, "--confirm-email", QA_EMAIL]


# --- it cannot delete a user, at all ----------------------------------------


def test_the_script_has_no_way_to_delete_a_user(qa_cleanup):
    """The property the standing grant rests on.

    Asserted against the source rather than behaviour: a flag added later
    would pass every behavioural test while widening what the granted
    command can do.
    """
    source = _SCRIPT_PATH.read_text()
    assert "DELETE FROM users" not in source
    assert "--user" not in source.replace("--user-id", "")


# --- scope: recipes ---------------------------------------------------------


def test_a_recipe_in_a_shared_book_is_refused(run_script, capsys):
    """Ownership alone is not enough — books are shareable.

    Deleting a recipe from a book with other members removes content
    those members can see, which is outside the scope this script's
    permission is granted on.
    """
    code, executed = run_script(
        [*BASE, "--recipe", RECIPE_ID, "--yes"], other_members=1
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "other member" in capsys.readouterr().err


def test_a_recipe_owned_by_someone_else_is_refused(run_script, capsys):
    code, executed = run_script(
        [*BASE, "--recipe", RECIPE_ID, "--yes"], owner_rows=0
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "not owned" in capsys.readouterr().err


def test_a_missing_recipe_is_refused(run_script):
    code, executed = run_script(
        [*BASE, "--recipe", RECIPE_ID, "--yes"], recipe_exists=False
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]


# --- scope: ingredients -----------------------------------------------------


def test_a_referenced_ingredient_is_never_deleted(run_script, capsys):
    """Rule 2. A row someone else's recipe uses must survive any id list."""
    code, executed = run_script(
        [*BASE, "--ingredient", INGREDIENT_ID, "--yes"],
        refs_before=1, refs_after=1,
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE FROM ingredients")]
    assert "still referenced" in capsys.readouterr().err


def test_an_ingredient_qualifies_once_its_owning_recipe_is_gone(run_script):
    """The ordering cc's wrinkle needs: recipe first, then the orphan.

    The banana rows are referenced while the junk recipes exist, and
    unreferenced immediately after — so the re-check has to happen inside
    the transaction, after the owned deletes, not before them.
    """
    code, executed = run_script(
        [*BASE, "--recipe", RECIPE_ID, "--ingredient", INGREDIENT_ID, "--yes"],
        refs_before=1, refs_after=0,
    )
    assert code == 0
    recipe_ix = next(
        i for i, s in enumerate(executed) if s.startswith("DELETE FROM recipes")
    )
    ing_ix = next(
        i for i, s in enumerate(executed)
        if s.startswith("DELETE FROM ingredients")
    )
    assert recipe_ix < ing_ix


def test_a_still_referenced_ingredient_rolls_the_whole_thing_back(
    run_script, capsys
):
    """If the re-check fails mid-transaction, nothing is left half-done."""
    code, executed = run_script(
        [*BASE, "--recipe", RECIPE_ID, "--ingredient", INGREDIENT_ID, "--yes"],
        refs_before=1, refs_after=1,
    )
    assert code == 1
    assert not [
        s for s in executed if s.startswith("DELETE FROM ingredients")
    ]
    assert "rolling back" in capsys.readouterr().err


# --- guards -----------------------------------------------------------------


def test_admin_is_refused_outright(run_script, capsys):
    code, executed = run_script(
        [*BASE, "--recipe", RECIPE_ID, "--yes"],
        user={"id": QA_ID, "email": QA_EMAIL, "name": "L", "is_admin": True},
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "admin" in capsys.readouterr().err.lower()


def test_mismatched_confirm_email_refuses(run_script):
    code, executed = run_script(
        ["--id-or-email", QA_EMAIL, "--confirm-email", "qa@exmaple.test",
         "--recipe", RECIPE_ID, "--yes"]
    )
    assert code == 1
    assert not [s for s in executed if s.startswith("DELETE")]


def test_dry_run_is_the_default(run_script, capsys):
    code, executed = run_script([*BASE, "--recipe", RECIPE_ID])
    assert code == 0
    assert not [s for s in executed if s.startswith("DELETE")]
    assert "Dry run" in capsys.readouterr().out


def test_commit_writes_an_audit_row(run_script):
    code, executed = run_script([*BASE, "--recipe", RECIPE_ID, "--yes"])
    assert code == 0
    audit = [s for s in executed if s.startswith("INSERT INTO error_logs")]
    assert len(audit) == 1 and "QaCleanupAudit" in audit[0]


# --- the assumption rule 2 rests on -----------------------------------------


def test_ingredients_are_not_a_shared_catalogue():
    """Rule 2 is only safe while ingredient rows are per-write.

    If `ingredients` ever becomes canonicalised — one row per real
    ingredient, shared across users — then "referenced by nothing" stops
    meaning "nobody else's data", and this script's reach silently
    widens. Pinned against the model's own docstring so that change
    fails here rather than in production.
    """
    source = _INGREDIENT_MODEL.read_text()
    assert "no identity semantics" in source.lower() or (
        "bag of display names" in source.lower()
    ), (
        "utils/models/ingredient.py no longer describes ingredients as a "
        "per-write bag of display names. qa_cleanup.py's rule 2 (delete an "
        "ingredient row when nothing references it) assumes exactly that. "
        "Re-derive the rule before changing this assertion."
    )
    assert "canonicalization" in source.lower()
