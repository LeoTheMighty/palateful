"""User-facing MCP tools — profile, preferences, and related read-only views."""

from __future__ import annotations

import json

from fastapi.encoders import jsonable_encoder
from mcp_server.auth import get_current_user
from mcp_server.server import mcp


@mcp.tool()
def get_profile() -> str:
    """Return the authenticated Palateful user's core profile.

    Use this when the user asks about themselves ("what's my name?", "which book
    am I in?") or when you need identifying info before personalising later
    responses. Returns name, email, username, onboarding state, and the ID
    of their default recipe book and shopping list.
    """
    user = get_current_user()
    data = {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "username": user.username,
        "has_completed_onboarding": user.has_completed_onboarding,
        "default_recipe_book_id": (
            str(user.default_recipe_book_id) if user.default_recipe_book_id else None
        ),
        "default_shopping_list_id": (
            str(user.default_shopping_list_id) if user.default_shopping_list_id else None
        ),
    }
    return json.dumps(jsonable_encoder(data), default=str)
