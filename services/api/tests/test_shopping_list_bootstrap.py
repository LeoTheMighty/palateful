"""Tests for shopping_list_bootstrap helpers.

Covers idempotency, no-op semantics, and the fact that callers are
responsible for committing in the set_default_if_missing path.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from api.v1.shopping_list.bootstrap import (
    DEFAULT_LIST_NAME,
    ensure_default_shopping_list,
    set_default_if_missing,
)


def _make_user(has_default: bool) -> MagicMock:
    """Build a user-shaped mock."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.default_shopping_list_id = uuid.uuid4() if has_default else None
    return user


def _make_db() -> MagicMock:
    """Build a session-shaped mock that captures add/flush/commit/refresh."""
    db = MagicMock()
    return db


# ---- set_default_if_missing ------------------------------------------------


def test_set_default_if_missing_sets_when_user_has_no_default():
    user = _make_user(has_default=False)
    shopping_list = MagicMock()
    shopping_list.id = uuid.uuid4()
    db = _make_db()

    result = set_default_if_missing(user, shopping_list, db)

    assert result is True
    assert user.default_shopping_list_id == shopping_list.id


def test_set_default_if_missing_is_noop_when_user_has_default():
    user = _make_user(has_default=True)
    original_default = user.default_shopping_list_id
    shopping_list = MagicMock()
    shopping_list.id = uuid.uuid4()
    db = _make_db()

    result = set_default_if_missing(user, shopping_list, db)

    assert result is False
    assert user.default_shopping_list_id == original_default


def test_set_default_if_missing_does_not_commit():
    """set_default_if_missing mutates session state but leaves commit
    responsibility to the caller."""
    user = _make_user(has_default=False)
    shopping_list = MagicMock()
    shopping_list.id = uuid.uuid4()
    db = _make_db()

    set_default_if_missing(user, shopping_list, db)

    db.commit.assert_not_called()


# ---- ensure_default_shopping_list ------------------------------------------


def test_ensure_default_returns_none_when_user_has_default():
    user = _make_user(has_default=True)
    db = _make_db()

    result = ensure_default_shopping_list(user, db)

    assert result is None
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_ensure_default_creates_and_commits_when_user_has_no_default():
    user = _make_user(has_default=False)
    db = _make_db()

    # Simulate flush populating the new list's id
    def flush_side_effect():
        # Walk the add() calls to find the ShoppingList and assign it an id.
        for call in db.add.call_args_list:
            list_obj = call.args[0]
            if list_obj.id is None:
                list_obj.id = uuid.uuid4()

    db.flush.side_effect = flush_side_effect

    result = ensure_default_shopping_list(user, db)

    assert result is not None
    assert result.name == DEFAULT_LIST_NAME
    assert result.owner_id == user.id
    # The user's default was pointed at the new list.
    assert user.default_shopping_list_id == result.id
    db.add.assert_called_once()
    db.commit.assert_called_once()
