"""Deadline calculation utilities for shopping list items."""

from datetime import datetime, timedelta
from typing import Literal

from utils.models.meal_event import MealEvent
from utils.models.shopping_list import ShoppingList, ShoppingListItem

# Due reason classifications
DUE_REASONS = {
    "marinate": "Needs time to marinate",
    "thaw": "Needs time to thaw",
    "rise": "Dough needs to rise",
    "brine": "Needs brining time",
    "chill": "Needs to chill/set",
    "soak": "Needs soaking time",
    "prep_start": "Prep begins",
    "cook_start": "Cooking begins",
    "serving": "Meal time",
}

# Wait types that require advance preparation
ADVANCE_PREP_WAIT_TYPES = {"marinate", "thaw", "rise", "brine", "chill", "soak", "freeze"}

UrgencyLevel = Literal["overdue", "urgent", "today", "soon", "normal", "none"]


def calculate_item_due_date(
    item: ShoppingListItem,
    meal_event: MealEvent | None = None,
    shopping_list: ShoppingList | None = None,
) -> tuple[datetime | None, str | None]:
    """
    Calculate when an ingredient is actually needed.

    Returns:
        Tuple of (due_at, due_reason)
    """
    # 1. Explicit due date on item (user override) - highest priority
    if item.due_at:
        return item.due_at, item.due_reason

    # 2. Based on meal event prep requirements
    effective_meal_event = meal_event
    if not effective_meal_event and item.meal_event_id:
        effective_meal_event = item.meal_event

    if effective_meal_event and effective_meal_event.recipe:
        recipe = effective_meal_event.recipe

        # Check if any recipe step requires advance prep for this ingredient
        lead_time_minutes = 0
        due_reason = "prep_start"

        for step in recipe.steps:
            if (
                step.wait_type in ADVANCE_PREP_WAIT_TYPES
                and step.wait_time_minutes
                and step.wait_time_minutes > lead_time_minutes
            ):
                # This step has a wait time that requires advance prep
                lead_time_minutes = step.wait_time_minutes
                due_reason = step.wait_type

        # Calculate due date
        prep_offset = effective_meal_event.prep_start_offset_minutes or 60
        base_time = effective_meal_event.scheduled_at - timedelta(minutes=prep_offset)

        if lead_time_minutes > 0:
            # Additional lead time for prep-ahead steps
            due_at = base_time - timedelta(minutes=lead_time_minutes)
            return due_at, due_reason
        else:
            # Default: due at prep start time
            return base_time, "prep_start"

    # 3. Based on meal event timing (no recipe)
    if effective_meal_event:
        prep_offset = effective_meal_event.prep_start_offset_minutes or 60
        due_at = effective_meal_event.scheduled_at - timedelta(minutes=prep_offset)
        return due_at, "prep_start"

    # 4. Based on shopping list's default deadline
    effective_list = shopping_list or item.shopping_list
    if effective_list and effective_list.default_deadline:
        return effective_list.default_deadline, None

    # 5. No deadline
    return None, None


def get_urgency_level(due_at: datetime | None, now: datetime | None = None) -> UrgencyLevel:
    """
    Determine urgency level for UI highlighting.

    Args:
        due_at: When the item is due
        now: Current time (defaults to now)

    Returns:
        Urgency level string
    """
    if not due_at:
        return "none"

    if now is None:
        now = datetime.now(due_at.tzinfo)

    time_remaining = due_at - now
    hours_until = time_remaining.total_seconds() / 3600

    if hours_until < 0:
        return "overdue"  # Red, past due
    elif hours_until < 2:
        return "urgent"  # Orange, very soon
    elif hours_until < 24:
        return "today"  # Yellow, same day
    elif hours_until < 72:
        return "soon"  # Blue, next few days
    else:
        return "normal"  # Gray, plenty of time


def get_urgency_priority(urgency: UrgencyLevel) -> int:
    """Get sort priority for urgency level (lower = more urgent)."""
    priorities = {
        "overdue": 0,
        "urgent": 1,
        "today": 2,
        "soon": 3,
        "normal": 4,
        "none": 5,
    }
    return priorities.get(urgency, 5)


def format_time_until(due_at: datetime, now: datetime | None = None) -> str:
    """
    Format a human-readable string for time until due.

    Args:
        due_at: When the item is due
        now: Current time (defaults to now)

    Returns:
        Human-readable time string
    """
    if now is None:
        now = datetime.now(due_at.tzinfo)

    diff = due_at - now
    total_minutes = int(diff.total_seconds() / 60)

    if total_minutes < 0:
        # Overdue
        abs_minutes = abs(total_minutes)
        if abs_minutes < 60:
            return f"{abs_minutes}m overdue"
        elif abs_minutes < 1440:
            hours = abs_minutes // 60
            return f"{hours}h overdue"
        else:
            days = abs_minutes // 1440
            return f"{days}d overdue"
    elif total_minutes < 60:
        return f"{total_minutes}m"
    elif total_minutes < 1440:
        hours = total_minutes // 60
        mins = total_minutes % 60
        if mins > 0:
            return f"{hours}h {mins}m"
        return f"{hours}h"
    else:
        days = total_minutes // 1440
        hours = (total_minutes % 1440) // 60
        if hours > 0:
            return f"{days}d {hours}h"
        return f"{days}d"


def calculate_recipe_lead_time(recipe) -> int:
    """
    Calculate total lead time needed for a recipe in minutes.

    This considers prep time, cook time, and any wait times
    that require advance preparation.

    Args:
        recipe: Recipe model instance

    Returns:
        Total lead time in minutes
    """
    total_minutes = 0

    # Add prep and cook time
    if recipe.prep_time:
        total_minutes += recipe.prep_time
    if recipe.cook_time:
        total_minutes += recipe.cook_time

    # Check for steps with wait times that require advance prep
    max_wait_minutes = 0
    for step in recipe.steps:
        if (
            step.wait_type in ADVANCE_PREP_WAIT_TYPES
            and step.wait_time_minutes
            and step.wait_time_minutes > max_wait_minutes
        ):
            max_wait_minutes = step.wait_time_minutes

    total_minutes += max_wait_minutes

    return total_minutes
