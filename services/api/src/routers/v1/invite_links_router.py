"""Invite links endpoints router."""

from api.v1.invite_links import (
    CreateInviteLink,
    DeactivateInviteLink,
    JoinViaLink,
    PreviewInviteLink,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

invite_links_router = APIRouter(prefix="/invite-links", tags=["invite-links"])


@invite_links_router.post("")
async def create_invite_link(
    params: CreateInviteLink.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a shareable invite link for a resource."""
    return CreateInviteLink.call(params, user=user, database=database)


@invite_links_router.get("/{token}")
async def preview_invite_link(
    token: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Preview invite link metadata and state."""
    return PreviewInviteLink.call(token=token, user=user, database=database)


@invite_links_router.post("/{token}/join")
async def join_via_link(
    token: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Join a resource via an invite link."""
    return JoinViaLink.call(token=token, user=user, database=database)


@invite_links_router.delete("/{invite_link_id}")
async def deactivate_invite_link(
    invite_link_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Deactivate an invite link."""
    return DeactivateInviteLink.call(invite_link_id=invite_link_id, user=user, database=database)
