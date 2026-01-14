"""State definition for the suggestion agent."""

from typing import TypedDict, Any


class PantryItem(TypedDict):
    """Pantry item data."""

    ingredient_name: str
    category: str | None
    quantity: float | None
    unit: str | None
    expires_at: str | None
    days_until_expiry: int | None
    expiring_soon: bool


class UserPreferences(TypedDict):
    """User preferences data."""

    user_id: str
    dietary_restrictions: list[str]
    cuisine_preferences: list[str]
    disliked_ingredients: list[str]
    cooking_skill_level: str
    preferred_meal_prep_time: int
    household_size: int
    notifications: dict[str, Any]


class RecipeMatch(TypedDict):
    """Recipe match from search."""

    id: str
    name: str
    description: str | None
    prep_time: int | None
    cook_time: int | None
    total_time: int
    servings: int
    relevance_score: float
    ingredients: list[dict[str, Any]]
    missing_ingredients: list[str]
    can_make: bool


class SuggestionOutput(TypedDict):
    """Generated suggestion output."""

    title: str
    body: str
    suggestion_type: str  # "recipe" | "meal_plan" | "tip" | "use_it_up"
    recipe_id: str | None
    trigger_context: dict[str, Any]


class SuggestionState(TypedDict, total=False):
    """
    State for the suggestion agent workflow.

    This TypedDict defines all the data that flows through the agent graph.
    """

    # Input state
    user_id: str
    trigger_type: str  # "daily" | "pantry_update" | "expiring"
    trigger_context: dict[str, Any]

    # Fetched context
    pantry_items: list[PantryItem]
    user_preferences: UserPreferences
    expiring_items: list[PantryItem]

    # Generated data
    matched_recipes: list[RecipeMatch]
    suggestions: list[SuggestionOutput]

    # Workflow state
    messages: list[dict[str, Any]]  # LLM conversation history
    current_step: str
    error: str | None

    # Output
    created_suggestion_ids: list[str]
    notifications_sent: int
