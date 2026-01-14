"""Node functions for the suggestion agent graph."""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from agent.graph.state import SuggestionState, SuggestionOutput
from agent.tools import GetPantryTool, GetUserPreferencesTool
from agent.llm import get_llm_provider, Message

logger = logging.getLogger(__name__)


def fetch_context(state: SuggestionState, db: Session) -> dict[str, Any]:
    """
    Fetch user context: pantry items, preferences, and expiring items.

    This node gathers all the information needed for the agent to make suggestions.
    """
    user_id = state["user_id"]
    trigger_type = state.get("trigger_type", "daily")

    logger.info(f"Fetching context for user {user_id}, trigger: {trigger_type}")

    # Get pantry items
    pantry_tool = GetPantryTool()
    pantry_result = pantry_tool.execute(db, user_id)

    pantry_items = []
    expiring_items = []

    if pantry_result.success and pantry_result.data:
        pantry_items = pantry_result.data.get("items", [])
        # Filter expiring items (within 3 days)
        expiring_items = [item for item in pantry_items if item.get("expiring_soon")]

    # Get user preferences
    prefs_tool = GetUserPreferencesTool()
    prefs_result = prefs_tool.execute(db, user_id)

    user_preferences = {}
    if prefs_result.success and prefs_result.data:
        user_preferences = prefs_result.data

    return {
        "pantry_items": pantry_items,
        "user_preferences": user_preferences,
        "expiring_items": expiring_items,
        "current_step": "context_fetched",
    }


def generate_suggestions(state: SuggestionState, db: Session) -> dict[str, Any]:
    """
    Generate meal suggestions using the LLM based on context.

    This node uses the LLM to analyze the user's situation and create
    personalized suggestions.
    """
    user_id = state["user_id"]
    trigger_type = state.get("trigger_type", "daily")
    pantry_items = state.get("pantry_items", [])
    expiring_items = state.get("expiring_items", [])
    user_preferences = state.get("user_preferences", {})

    logger.info(f"Generating suggestions for user {user_id}")

    # Build context for the LLM
    context_parts = []

    # Pantry summary
    if pantry_items:
        ingredients_by_category = {}
        for item in pantry_items:
            cat = item.get("category", "other")
            if cat not in ingredients_by_category:
                ingredients_by_category[cat] = []
            ingredients_by_category[cat].append(item["ingredient_name"])

        context_parts.append("**Available Ingredients:**")
        for cat, ingredients in ingredients_by_category.items():
            context_parts.append(f"- {cat}: {', '.join(ingredients[:10])}")

    # Expiring items
    if expiring_items:
        expiring_names = [f"{item['ingredient_name']} ({item.get('days_until_expiry', 0)} days)"
                        for item in expiring_items[:5]]
        context_parts.append(f"\n**Expiring Soon:** {', '.join(expiring_names)}")

    # User preferences
    if user_preferences:
        if user_preferences.get("dietary_restrictions"):
            context_parts.append(f"\n**Dietary Restrictions:** {', '.join(user_preferences['dietary_restrictions'])}")
        if user_preferences.get("cuisine_preferences"):
            context_parts.append(f"**Preferred Cuisines:** {', '.join(user_preferences['cuisine_preferences'])}")

    context = "\n".join(context_parts) if context_parts else "No pantry data available."

    # Create the prompt based on trigger type
    if trigger_type == "daily":
        prompt = f"""Based on the user's available ingredients, suggest a meal for today.

{context}

Please provide:
1. A specific meal suggestion with a catchy name
2. Why this meal is a good choice for today
3. Any quick tips for preparation

Keep the suggestion practical and achievable for a home cook."""

    elif trigger_type == "pantry_update":
        prompt = f"""The user just updated their pantry. Based on their new ingredients, suggest what they could make.

{context}

Please provide:
1. 2-3 quick meal ideas using their new ingredients
2. Which ingredients would work well together
3. Any meal prep suggestions for the week

Keep suggestions practical and focused on the newly added items."""

    elif trigger_type == "expiring":
        prompt = f"""Some ingredients are about to expire! Help the user use them up.

{context}

Please provide:
1. A specific recipe idea that uses the expiring ingredients
2. Why this helps reduce food waste
3. Tips for storing any leftovers

Prioritize using the expiring ingredients first!"""

    else:
        prompt = f"""Suggest a meal based on available ingredients.

{context}

Please provide a helpful meal suggestion."""

    # Call the LLM
    provider = get_llm_provider()
    messages = [
        Message(
            role="system",
            content="""You are a helpful meal planning assistant for the Palateful app.
Your goal is to provide practical, delicious meal suggestions based on what ingredients
the user has available. Be concise, friendly, and focus on making cooking enjoyable.
Keep responses under 200 words.""",
        ),
        Message(role="user", content=prompt),
    ]

    response = provider.chat(messages, temperature=0.7)

    # Create suggestion output
    suggestion_type = "use_it_up" if trigger_type == "expiring" else "recipe"

    suggestions = [
        SuggestionOutput(
            title=_extract_title(response.content, trigger_type),
            body=response.content,
            suggestion_type=suggestion_type,
            recipe_id=None,  # Could be linked if we searched for a matching recipe
            trigger_context={
                "trigger_type": trigger_type,
                "pantry_count": len(pantry_items),
                "expiring_count": len(expiring_items),
            },
        )
    ]

    return {
        "suggestions": suggestions,
        "messages": [{"role": "assistant", "content": response.content}],
        "current_step": "suggestions_generated",
    }


def _extract_title(content: str, trigger_type: str) -> str:
    """Extract a title from the LLM response or generate a default."""
    # Try to find a title in the first line
    first_line = content.split("\n")[0].strip()

    # Remove markdown formatting
    title = first_line.lstrip("#").strip()
    title = title.strip("*").strip()

    # If the first line looks like a title (short enough), use it
    if len(title) <= 60 and len(title) > 0:
        return title

    # Otherwise, generate a default title
    titles = {
        "daily": "Today's Meal Suggestion",
        "pantry_update": "New Ingredient Ideas",
        "expiring": "Use It Up: Expiring Soon",
    }
    return titles.get(trigger_type, "Meal Suggestion")


def create_notifications(state: SuggestionState, db: Session) -> dict[str, Any]:
    """
    Create suggestions and notifications in the database.

    This node persists the generated suggestions and triggers notifications.
    """
    from utils.models import Suggestion, Notification

    user_id = state["user_id"]
    suggestions = state.get("suggestions", [])
    trigger_type = state.get("trigger_type", "daily")

    logger.info(f"Creating {len(suggestions)} suggestions for user {user_id}")

    created_ids = []
    notifications_sent = 0

    for suggestion_data in suggestions:
        # Create suggestion record
        suggestion = Suggestion(
            user_id=user_id,
            title=suggestion_data["title"],
            body=suggestion_data["body"],
            suggestion_type=suggestion_data["suggestion_type"],
            recipe_id=suggestion_data.get("recipe_id"),
            trigger_type=trigger_type,
            trigger_context=suggestion_data.get("trigger_context", {}),
            expires_at=datetime.utcnow() + timedelta(days=7),  # Expire after 7 days
        )
        db.add(suggestion)
        db.flush()  # Get the ID

        created_ids.append(str(suggestion.id))

        # Create in-app notification
        notification = Notification(
            user_id=user_id,
            title=suggestion_data["title"],
            body=suggestion_data["body"][:200] + "..." if len(suggestion_data["body"]) > 200 else suggestion_data["body"],
            notification_type="suggestion",
            channel="in_app",
            status="sent",
            suggestion_id=suggestion.id,
            sent_at=datetime.utcnow(),
        )
        db.add(notification)
        notifications_sent += 1

    db.commit()

    logger.info(f"Created {len(created_ids)} suggestions, {notifications_sent} notifications")

    return {
        "created_suggestion_ids": created_ids,
        "notifications_sent": notifications_sent,
        "current_step": "completed",
    }


def handle_error(state: SuggestionState, db: Session) -> dict[str, Any]:
    """Handle errors in the workflow."""
    error = state.get("error", "Unknown error")
    logger.error(f"Agent workflow error: {error}")

    return {
        "current_step": "error",
        "error": error,
    }
