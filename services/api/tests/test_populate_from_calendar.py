"""Tests for PopulateFromCalendar endpoint."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import (
    MockIngredient,
    MockMealEvent,
    MockQuery,
    MockRecipe,
    MockRecipeIngredient,
    MockShoppingList,
    MockShoppingListItem,
    MockShoppingListUser,
)


def make_meal_event_with_recipe(owner_id, ingredient_name="Pasta", category="Dry Goods"):
    """Helper: meal event with a recipe containing one ingredient."""
    ingredient_id = str(uuid.uuid4())
    recipe_id = str(uuid.uuid4())

    ingredient = MockIngredient(id=ingredient_id, canonical_name=ingredient_name, category=category)
    ri = MockRecipeIngredient(
        ingredient_id=ingredient_id,
        recipe_id=recipe_id,
        quantity_display=Decimal("200.000"),
        unit_display="g",
    )
    ri.ingredient = ingredient

    recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
    recipe.ingredients = [ri]
    recipe.steps = []

    event = MockMealEvent(
        owner_id=str(owner_id),
        status="planned",
        scheduled_at=datetime.now(UTC),
        recipe=recipe,
        recipe_id=recipe_id,
    )
    return event, recipe, ingredient_id


class TestPopulateFromCalendarSuccess:
    """Core success path — meal events with recipes add ingredients."""

    def test_success_adds_ingredients_from_meal_event(self, client, mock_db, mock_user):
        """Ingredients from a planned meal event are added to the shopping list."""
        list_id = str(uuid.uuid4())

        event, recipe, ingredient_id = make_meal_event_with_recipe(mock_user.id)
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([event])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-17", "end_date": "2026-03-23"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 1
        assert data["items_skipped"] == 0
        assert data["meal_events_included"] == 1
        assert len(data["meal_events"]) == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["unit"] == "g"

    def test_success_returns_zero_when_no_meal_events(self, client, mock_db, mock_user):
        """Returns items_added=0 and meal_events_included=0 when no events in range."""
        list_id = str(uuid.uuid4())
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-17", "end_date": "2026-03-23"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["items_skipped"] == 0
        assert data["meal_events_included"] == 0
        assert data["meal_events"] == []

    def test_success_skips_events_without_recipe(self, client, mock_db, mock_user):
        """Meal events without a linked recipe are skipped without error."""
        list_id = str(uuid.uuid4())

        event_no_recipe = MockMealEvent(
            owner_id=str(mock_user.id),
            status="planned",
            recipe=None,
            recipe_id=None,
        )
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([event_no_recipe])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-17", "end_date": "2026-03-23"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["meal_events_included"] == 0


class TestPopulateFromCalendarDeduplication:
    """Items already in the list for the same meal event are skipped."""

    def test_skips_duplicate_ingredient_for_same_meal_event(self, client, mock_db, mock_user):
        """If (ingredient_id, meal_event_id) already in list, it is skipped."""
        list_id = str(uuid.uuid4())

        event, recipe, ingredient_id = make_meal_event_with_recipe(mock_user.id)

        # Existing item keyed on (ingredient_id, meal_event_id)
        existing_item = MockShoppingListItem(
            shopping_list_id=list_id,
            ingredient_id=ingredient_id,
            meal_event_id=event.id,
        )
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[existing_item])

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.db.query.return_value = MockQuery([event])

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-17", "end_date": "2026-03-23"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["items_skipped"] == 1


class TestPopulateFromCalendarAccessControl:
    """Access control — only owners/editors can populate."""

    def test_returns_403_for_non_member(self, client, mock_db, mock_user):
        """User without access to the list gets 403."""
        list_id = str(uuid.uuid4())
        other_owner_id = str(uuid.uuid4())

        sl = MockShoppingList(id=list_id, owner_id=other_owner_id, items=[])

        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        mock_db.set_find_by(ShoppingList, sl, id=list_id)
        mock_db.set_find_by(
            ShoppingListUser,
            None,
            shopping_list_id=list_id,
            user_id=str(mock_user.id),
        )

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-17", "end_date": "2026-03-23"},
        )

        assert response.status_code == 403

    def test_returns_404_for_missing_list(self, client, mock_db, mock_user):
        """Missing shopping list returns 404."""
        list_id = str(uuid.uuid4())

        from utils.models.shopping_list import ShoppingList

        mock_db.set_find_by(ShoppingList, None, id=list_id)

        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-calendar",
            json={"start_date": "2026-03-17", "end_date": "2026-03-23"},
        )

        assert response.status_code == 404
