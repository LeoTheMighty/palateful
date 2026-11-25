"""Invitations endpoints router.

aam-21: flipped to `get_async_database` + `get_current_user_async`.
Push-notification fan-out (Firebase Admin) runs through
`run_in_threadpool` inside the handlers — the same threadpool hop the
aam-8 `send_to_user_async` variant performs internally, so the explicit
wrap stays.
"""

from api.v1.invitations import (
    AcceptInvitation,
    ClaimInvitations,
    DeclineInvitation,
    ListReceivedInvitations,
    ListSentInvitations,
    RevokeInvitation,
    SendInvitation,
)
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

invitations_router = APIRouter(prefix="/invitations", tags=["invitations"])


# ============================================================
# Send & Claim
# ============================================================


@invitations_router.post("")
async def send_invitation(
    params: SendInvitation.Params,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Send an invitation to share a resource."""
    return await SendInvitation.call(params, user=user, database=database)


@invitations_router.post("/claim")
async def claim_invitations(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Claim pending email invitations after signup."""
    return await ClaimInvitations.call(user=user, database=database)


# ============================================================
# List (defined before /{invitation_id} to avoid route conflicts)
# ============================================================


@invitations_router.get("")
async def list_received_invitations(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List pending invitations received by the current user."""
    return await ListReceivedInvitations.call(user=user, database=database)


@invitations_router.get("/sent")
async def list_sent_invitations(
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List invitations sent by the current user."""
    return await ListSentInvitations.call(user=user, database=database)


# ============================================================
# Actions on specific invitation
# ============================================================


@invitations_router.post("/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Accept an invitation."""
    return await AcceptInvitation.call(
        invitation_id=invitation_id, user=user, database=database
    )


@invitations_router.post("/{invitation_id}/decline")
async def decline_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Decline an invitation."""
    return await DeclineInvitation.call(
        invitation_id=invitation_id, user=user, database=database
    )


@invitations_router.delete("/{invitation_id}")
async def revoke_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Revoke a sent invitation."""
    return await RevokeInvitation.call(
        invitation_id=invitation_id, user=user, database=database
    )
