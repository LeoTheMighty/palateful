"""Shared helpers for invitation and invite link endpoints."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from utils.api.endpoint import APIException
from utils.classes.error_code import ErrorCode
from utils.models.calendar import Calendar
from utils.models.calendar_user import CalendarUser
from utils.models.meal_event import MealEvent
from utils.models.meal_event_participant import MealEventParticipant
from utils.models.pantry import Pantry
from utils.models.pantry_user import PantryUser
from utils.models.recipe_book import RecipeBook
from utils.models.recipe_book_user import RecipeBookUser
from utils.models.shopping_list import ShoppingList
from utils.models.shopping_list_user import ShoppingListUser

# Valid resource_type → role_offered mappings
VALID_ROLES = {
    "recipe_book": {"editor", "viewer"},
    "pantry": {"editor", "viewer"},
    "shopping_list": {"editor", "viewer"},
    "meal_event": {"cohost", "guest"},
    "calendar": {"editor"},
}

VALID_RESOURCE_TYPES = set(VALID_ROLES.keys())


def validate_resource_and_role(resource_type: str, role_offered: str) -> None:
    """Validate that the resource_type and role_offered combination is legal."""
    if resource_type not in VALID_RESOURCE_TYPES:
        raise APIException(
            status_code=400,
            detail=f"Invalid resource type: {resource_type}",
            code=ErrorCode.INVITATION_INVALID_RESOURCE_TYPE,
        )
    if role_offered not in VALID_ROLES[resource_type]:
        valid = ", ".join(sorted(VALID_ROLES[resource_type]))
        raise APIException(
            status_code=400,
            detail=f"Invalid role '{role_offered}' for {resource_type}. Valid: {valid}",
            code=ErrorCode.INVITATION_INVALID_ROLE,
        )


def check_resource_permission(
    db: Session,
    user_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
) -> None:
    """Check that user has owner/editor permission on the resource. Raises on failure."""
    if resource_type == "recipe_book":
        membership = db.execute(
            select(RecipeBookUser).where(
                RecipeBookUser.user_id == user_id,
                RecipeBookUser.recipe_book_id == resource_id,
                RecipeBookUser.archived_at.is_(None),
            )
        ).scalar_one_or_none()
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to invite to this recipe book",
                code=ErrorCode.RECIPE_BOOK_ACCESS_DENIED,
            )

    elif resource_type == "pantry":
        membership = db.execute(
            select(PantryUser).where(
                PantryUser.user_id == user_id,
                PantryUser.pantry_id == resource_id,
                PantryUser.archived_at.is_(None),
            )
        ).scalar_one_or_none()
        if not membership or membership.role not in ("owner", "editor"):
            raise APIException(
                status_code=403,
                detail="You don't have permission to invite to this pantry",
                code=ErrorCode.FORBIDDEN,
            )

    elif resource_type == "shopping_list":
        shopping_list = db.execute(
            select(ShoppingList).where(
                ShoppingList.id == resource_id,
                ShoppingList.archived_at.is_(None),
            )
        ).scalar_one_or_none()
        if not shopping_list:
            raise APIException(
                status_code=404,
                detail="Shopping list not found",
                code=ErrorCode.SHOPPING_LIST_NOT_FOUND,
            )
        if shopping_list.owner_id != user_id:
            membership = db.execute(
                select(ShoppingListUser).where(
                    ShoppingListUser.user_id == user_id,
                    ShoppingListUser.shopping_list_id == resource_id,
                    ShoppingListUser.archived_at.is_(None),
                )
            ).scalar_one_or_none()
            if not membership or membership.role not in ("owner", "editor"):
                raise APIException(
                    status_code=403,
                    detail="You don't have permission to invite to this shopping list",
                    code=ErrorCode.SHOPPING_LIST_ACCESS_DENIED,
                )

    elif resource_type == "meal_event":
        meal_event = db.execute(
            select(MealEvent).where(
                MealEvent.id == resource_id,
                MealEvent.archived_at.is_(None),
            )
        ).scalar_one_or_none()
        if not meal_event:
            raise APIException(
                status_code=404,
                detail="Meal event not found",
                code=ErrorCode.MEAL_EVENT_NOT_FOUND,
            )
        if meal_event.owner_id != user_id:
            participant = db.execute(
                select(MealEventParticipant).where(
                    MealEventParticipant.user_id == user_id,
                    MealEventParticipant.meal_event_id == resource_id,
                    MealEventParticipant.archived_at.is_(None),
                )
            ).scalar_one_or_none()
            if not participant or participant.role not in ("host", "cohost"):
                raise APIException(
                    status_code=403,
                    detail="You don't have permission to invite to this meal event",
                    code=ErrorCode.MEAL_EVENT_ACCESS_DENIED,
                )

    elif resource_type == "calendar":
        calendar = db.execute(
            select(Calendar).where(
                Calendar.id == resource_id,
                Calendar.archived_at.is_(None),
            )
        ).scalar_one_or_none()
        if not calendar:
            raise APIException(
                status_code=404,
                detail="Calendar not found",
                code=ErrorCode.CALENDAR_NOT_FOUND,
            )
        membership = db.execute(
            select(CalendarUser).where(
                CalendarUser.user_id == user_id,
                CalendarUser.calendar_id == resource_id,
                CalendarUser.archived_at.is_(None),
            )
        ).scalar_one_or_none()
        if not membership or membership.role != "owner":
            raise APIException(
                status_code=403,
                detail="Only the calendar owner can invite new members",
                code=ErrorCode.CALENDAR_ACCESS_DENIED,
            )
    else:  # pragma: no cover — resource_type validated before call
        pass


def check_existing_membership(
    db: Session,
    user_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
) -> bool:
    """Return True if user is already an active member of the resource."""
    if resource_type == "recipe_book":
        return db.execute(
            select(RecipeBookUser).where(
                RecipeBookUser.user_id == user_id,
                RecipeBookUser.recipe_book_id == resource_id,
                RecipeBookUser.archived_at.is_(None),
            )
        ).scalar_one_or_none() is not None

    elif resource_type == "pantry":
        return db.execute(
            select(PantryUser).where(
                PantryUser.user_id == user_id,
                PantryUser.pantry_id == resource_id,
                PantryUser.archived_at.is_(None),
            )
        ).scalar_one_or_none() is not None

    elif resource_type == "shopping_list":
        sl = db.execute(
            select(ShoppingList).where(ShoppingList.id == resource_id)
        ).scalar_one_or_none()
        if sl and sl.owner_id == user_id:
            return True
        return db.execute(
            select(ShoppingListUser).where(
                ShoppingListUser.user_id == user_id,
                ShoppingListUser.shopping_list_id == resource_id,
                ShoppingListUser.archived_at.is_(None),
            )
        ).scalar_one_or_none() is not None

    elif resource_type == "meal_event":
        me = db.execute(
            select(MealEvent).where(MealEvent.id == resource_id)
        ).scalar_one_or_none()
        if me and me.owner_id == user_id:
            return True
        return db.execute(
            select(MealEventParticipant).where(
                MealEventParticipant.user_id == user_id,
                MealEventParticipant.meal_event_id == resource_id,
                MealEventParticipant.archived_at.is_(None),
            )
        ).scalar_one_or_none() is not None

    elif resource_type == "calendar":
        return db.execute(
            select(CalendarUser).where(
                CalendarUser.user_id == user_id,
                CalendarUser.calendar_id == resource_id,
                CalendarUser.archived_at.is_(None),
            )
        ).scalar_one_or_none() is not None

    return False  # pragma: no cover — resource_type validated before call


def create_membership(
    db: Session,
    user_id: uuid.UUID,
    resource_type: str,
    resource_id: uuid.UUID,
    role: str,
    invited_by_id: uuid.UUID | None = None,
) -> None:
    """Create a membership row in the appropriate join table.

    Handles reactivation of archived memberships and is idempotent
    (does nothing if already an active member).
    """
    if resource_type == "recipe_book":
        existing = db.execute(
            select(RecipeBookUser).where(
                RecipeBookUser.user_id == user_id,
                RecipeBookUser.recipe_book_id == resource_id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.archived_at is not None:
                existing.archived_at = None
                existing.role = role
                existing.invited_by_id = invited_by_id
            # Already active — idempotent
        else:
            db.add(RecipeBookUser(
                user_id=user_id,
                recipe_book_id=resource_id,
                role=role,
                invited_by_id=invited_by_id,
            ))

    elif resource_type == "pantry":
        existing = db.execute(
            select(PantryUser).where(
                PantryUser.user_id == user_id,
                PantryUser.pantry_id == resource_id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.archived_at is not None:
                existing.archived_at = None
                existing.role = role
                existing.invited_by_id = invited_by_id
        else:
            db.add(PantryUser(
                user_id=user_id,
                pantry_id=resource_id,
                role=role,
                invited_by_id=invited_by_id,
            ))

    elif resource_type == "shopping_list":
        existing = db.execute(
            select(ShoppingListUser).where(
                ShoppingListUser.user_id == user_id,
                ShoppingListUser.shopping_list_id == resource_id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.archived_at is not None:
                existing.archived_at = None
                existing.role = role
                existing.invited_by_id = invited_by_id
        else:
            db.add(ShoppingListUser(
                user_id=user_id,
                shopping_list_id=resource_id,
                role=role,
                invited_by_id=invited_by_id,
            ))
        # Mark shopping list as shared
        shopping_list = db.execute(
            select(ShoppingList).where(ShoppingList.id == resource_id)
        ).scalar_one_or_none()
        if shopping_list and not shopping_list.is_shared:
            shopping_list.is_shared = True

    elif resource_type == "meal_event":
        existing = db.execute(
            select(MealEventParticipant).where(
                MealEventParticipant.user_id == user_id,
                MealEventParticipant.meal_event_id == resource_id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.archived_at is not None:
                existing.archived_at = None
                existing.role = role
                existing.invited_by_id = invited_by_id
                existing.status = "accepted"
        else:
            db.add(MealEventParticipant(
                user_id=user_id,
                meal_event_id=resource_id,
                role=role,
                invited_by_id=invited_by_id,
                status="accepted",
            ))

    elif resource_type == "calendar":
        existing = db.execute(
            select(CalendarUser).where(
                CalendarUser.user_id == user_id,
                CalendarUser.calendar_id == resource_id,
            )
        ).scalar_one_or_none()
        if existing:
            if existing.archived_at is not None:
                existing.archived_at = None
                existing.role = role
                existing.invited_by_id = invited_by_id
        else:
            db.add(CalendarUser(
                user_id=user_id,
                calendar_id=resource_id,
                role=role,
                invited_by_id=invited_by_id,
            ))
    else:  # pragma: no cover — resource_type validated before call
        pass

    db.flush()


def get_resource_name(
    db: Session,
    resource_type: str,
    resource_id: uuid.UUID,
) -> str | None:
    """Return the display name for a resource."""
    if resource_type == "recipe_book":
        rb = db.execute(
            select(RecipeBook.name).where(RecipeBook.id == resource_id)
        ).scalar_one_or_none()
        return rb

    elif resource_type == "pantry":
        p = db.execute(
            select(Pantry.name).where(Pantry.id == resource_id)
        ).scalar_one_or_none()
        return p

    elif resource_type == "shopping_list":
        sl = db.execute(
            select(ShoppingList.name).where(ShoppingList.id == resource_id)
        ).scalar_one_or_none()
        return sl or "Shopping List"

    elif resource_type == "meal_event":
        me = db.execute(
            select(MealEvent.title).where(MealEvent.id == resource_id)
        ).scalar_one_or_none()
        return me

    elif resource_type == "calendar":
        cal = db.execute(
            select(Calendar.name).where(Calendar.id == resource_id)
        ).scalar_one_or_none()
        return cal

    return None
