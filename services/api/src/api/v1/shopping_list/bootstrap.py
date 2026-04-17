"""Shopping-list bootstrap helpers — single source of truth for the
'every user has a default shopping list' invariant.

Three callers use these helpers:

  1. complete_onboarding — post-commit hook creates a default list for
     every new user so their Cart tab is never empty-by-default.
  2. CreateShoppingList — when a user manually creates their first list,
     it's auto-set as default.
  3. migration backfill (services/migrator/migrations/...) — one-shot
     sweep that covers historically-onboarded users who were created
     before the post-commit hook existed.

All three paths are idempotent: if the user already has a default, the
helper returns without writing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from utils.models.shopping_list import ShoppingList

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from utils.models.user import User


logger = logging.getLogger(__name__)

# Keep this label stable — the migration backfill matches on it for
# reattribution during replay scenarios.
DEFAULT_LIST_NAME = "Shopping List"


def set_default_if_missing(
    user: User,
    shopping_list: ShoppingList,
    db: Session,
) -> bool:
    """Set `shopping_list` as the user's default only if they have none.

    Returns True if the default was set, False if the user already had one.
    Callers are responsible for committing — this function mutates the
    session but does not commit.
    """
    if user.default_shopping_list_id is not None:
        return False
    user.default_shopping_list_id = shopping_list.id
    return True


def ensure_default_shopping_list(
    user: User,
    db: Session,
) -> ShoppingList | None:
    """Idempotently ensure the user has a default shopping list.

    If the user already has `default_shopping_list_id`, returns None.
    Otherwise creates a new list named "Shopping List" owned by the user,
    sets it as default, commits, and returns the created list.

    This is the single code path used by:
      - onboarding (via a post-commit hook)
      - the migration backfill for existing users

    Errors are allowed to propagate; callers that can tolerate failure
    (e.g. the onboarding post-commit hook) are responsible for catching
    and logging.
    """
    if user.default_shopping_list_id is not None:
        return None

    shopping_list = ShoppingList(
        name=DEFAULT_LIST_NAME,
        owner_id=user.id,
    )
    db.add(shopping_list)
    db.flush()  # get the list id

    user.default_shopping_list_id = shopping_list.id
    db.commit()
    db.refresh(shopping_list)

    logger.info(
        "shopping_list_bootstrap.created_default",
        extra={
            "user_id": str(user.id),
            "shopping_list_id": str(shopping_list.id),
        },
    )
    return shopping_list
