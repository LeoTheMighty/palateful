"""Invitations endpoints router."""

from api.v1.invitations import (
    AcceptInvitation,
    ClaimInvitations,
    DeclineInvitation,
    ListReceivedInvitations,
    ListSentInvitations,
    RevokeInvitation,
    SendInvitation,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

invitations_router = APIRouter(prefix="/invitations", tags=["invitations"])


# ============================================================
# Send & Claim
# ============================================================


@invitations_router.post("")
async def send_invitation(
    params: SendInvitation.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Send an invitation to share a resource."""
    return SendInvitation.call(params, user=user, database=database)


@invitations_router.post("/claim")
async def claim_invitations(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Claim pending email invitations after signup."""
    return ClaimInvitations.call(user=user, database=database)


# ============================================================
# List (defined before /{invitation_id} to avoid route conflicts)
# ============================================================


@invitations_router.get("")
async def list_received_invitations(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List pending invitations received by the current user."""
    return ListReceivedInvitations.call(user=user, database=database)


@invitations_router.get("/sent")
async def list_sent_invitations(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List invitations sent by the current user."""
    return ListSentInvitations.call(user=user, database=database)


# ============================================================
# Actions on specific invitation
# ============================================================


@invitations_router.post("/{invitation_id}/accept")
async def accept_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Accept an invitation."""
    return AcceptInvitation.call(invitation_id=invitation_id, user=user, database=database)


@invitations_router.post("/{invitation_id}/decline")
async def decline_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Decline an invitation."""
    return DeclineInvitation.call(invitation_id=invitation_id, user=user, database=database)


@invitations_router.delete("/{invitation_id}")
async def revoke_invitation(
    invitation_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Revoke a sent invitation."""
    return RevokeInvitation.call(invitation_id=invitation_id, user=user, database=database)
