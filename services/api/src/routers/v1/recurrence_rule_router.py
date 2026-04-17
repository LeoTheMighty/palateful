"""Recurrence rule endpoints router."""

from datetime import date

from api.v1.recurrence_rule import (
    CreateRecurrenceRule,
    DeleteRecurrenceRule,
    GetRecurrenceRule,
    ListRecurrenceRules,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

recurrence_rule_router = APIRouter(tags=["recurrence-rules"])


@recurrence_rule_router.get("/recurrence-rules")
async def list_recurrence_rules(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List recurrence rules visible to the current user."""
    return ListRecurrenceRules.call(user=user, database=database)


@recurrence_rule_router.post("/recurrence-rules")
async def create_recurrence_rule(
    params: CreateRecurrenceRule.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a new recurrence rule."""
    return CreateRecurrenceRule.call(
        params=params,
        user=user,
        database=database,
    )


@recurrence_rule_router.get("/recurrence-rules/{rule_id}")
async def get_recurrence_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a recurrence rule."""
    return GetRecurrenceRule.call(
        rule_id=rule_id,
        user=user,
        database=database,
    )


@recurrence_rule_router.delete("/recurrence-rules/{rule_id}")
async def delete_recurrence_rule(
    rule_id: str,
    scope: str = "series",
    occurrence_date: date | None = None,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive (or split) a recurrence rule."""
    return DeleteRecurrenceRule.call(
        rule_id=rule_id,
        scope=scope,
        occurrence_date=occurrence_date,
        user=user,
        database=database,
    )
