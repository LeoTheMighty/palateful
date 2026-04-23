"""Invite links endpoints router.

aam-21: flipped to `get_async_database` + `get_current_user_async`.
"""

from api.v1.invite_links import (
    CreateInviteLink,
    DeactivateInviteLink,
    JoinViaLink,
    PreviewInviteLink,
)
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

invite_links_router = APIRouter(prefix="/invite-links", tags=["invite-links"])


@invite_links_router.post("")
async def create_invite_link(
    params: CreateInviteLink.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Create a shareable invite link for a resource."""
    return await CreateInviteLink.call(params, user=user, database=database)


@invite_links_router.get("/{token}")
async def preview_invite_link(
    token: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Preview invite link metadata and state."""
    return await PreviewInviteLink.call(
        token=token, user=user, database=database
    )


@invite_links_router.post("/{token}/join")
async def join_via_link(
    token: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Join a resource via an invite link."""
    return await JoinViaLink.call(token=token, user=user, database=database)


@invite_links_router.delete("/{invite_link_id}")
async def deactivate_invite_link(
    invite_link_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Deactivate an invite link."""
    return await DeactivateInviteLink.call(
        invite_link_id=invite_link_id, user=user, database=database
    )
