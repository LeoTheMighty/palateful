"""mcal-5: tests for `POST /v1/meal-events/{event_id}/add-to-shopping-list`."""

import uuid
from decimal import Decimal

from conftest import (
    MockExecuteResult,
    MockMealEvent,
    MockModel,
    MockQuery,
    MockRecipe,
)


class MockMeal(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "name": "Kale Salad Meal",
            "description": None,
            "recipe_book_id": str(uuid.uuid4()),
            "share_token": None,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockMealRecipe(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "meal_id": str(uuid.uuid4()),
            "recipe_id": str(uuid.uuid4()),
            "order_index": 0,
            "recipe": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockShoppingList(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "name": "Groceries",
            "owner_id": str(uuid.uuid4()),
            "share_code": None,
            "items": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockShoppingListItem(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "name": "olive oil",
            "ingredient_id": str(uuid.uuid4()),
            "shopping_list_id": str(uuid.uuid4()),
            "recipe_id": None,
            "meal_event_id": None,
            "source_meal_id": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockIngredient(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "canonical_name": "olive oil",
            "category": "oils",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class MockRecipeIngredient(MockModel):
    def __init__(self, *, ingredient, **kwargs):
        defaults = {
            "ingredient": ingredient,
            "ingredient_id": ingredient.id,
            "quantity_display": Decimal("1"),
            "unit_display": "tbsp",
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class TestRecipeLinkedEvent:
    def test_recipe_event_expands_via_recipe_ingredients(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        olive = MockIngredient(id=str(uuid.uuid4()))
        recipe = MockRecipe(id=str(uuid.uuid4()), name="Pizza")
        recipe.ingredients = [MockRecipeIngredient(ingredient=olive)]
        event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe=recipe,
            recipe_id=recipe.id,
            meal_id=None,
            meal=None,
        )
        list_obj = MockShoppingList(id=str(uuid.uuid4()), owner_id=mock_user.id)
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 1
        assert data["items"][0]["recipe_id"] == recipe.id
        assert data["items"][0]["meal_event_id"] == event.id
        assert data["items"][0]["source_meal_id"] is None


class TestMealLinkedEvent:
    def test_meal_event_expands_via_aggregate(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        olive = MockIngredient(id=str(uuid.uuid4()))
        r1 = MockRecipe(id=str(uuid.uuid4()))
        r1.recipe_book = None
        r1.ingredients = [MockRecipeIngredient(ingredient=olive)]
        r2 = MockRecipe(id=str(uuid.uuid4()))
        r2.recipe_book = None
        r2.ingredients = [MockRecipeIngredient(ingredient=olive)]
        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[
                MockMealRecipe(recipe=r1, order_index=0),
                MockMealRecipe(recipe=r2, order_index=1),
            ],
        )
        event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe=None,
            recipe_id=None,
            meal_id=meal.id,
            meal=meal,
        )
        list_obj = MockShoppingList(id=str(uuid.uuid4()), owner_id=mock_user.id)
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        # No dedup post-str-ing-2: each component contributes its own row in
        # components × ingredients order. Two adjacent "olive oil" lines, one
        # per component, each retaining its 1-tbsp quantity.
        assert data["items_added"] == 2
        assert Decimal(data["items"][0]["quantity"]) == Decimal("1")
        assert Decimal(data["items"][1]["quantity"]) == Decimal("1")
        assert data["items"][0]["meal_event_id"] == event.id
        assert data["items"][1]["meal_event_id"] == event.id
        assert data["items"][0]["source_meal_id"] == meal.id
        assert data["items"][1]["source_meal_id"] == meal.id
        assert data["items"][0]["recipe_id"] is None
        assert data["items"][1]["recipe_id"] is None


class TestEdges:
    def test_404_when_event_missing(self, client, mock_async_db, mock_user):
        response = client.post(
            f"/v1/meal-events/{uuid.uuid4()}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_422_for_freetext_event(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        event = MockMealEvent(
            id=str(uuid.uuid4()),
            owner_id=mock_user.id,
            recipe_id=None,
            meal_id=None,
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[event])
        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 422

    def test_404_when_shopping_list_missing(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent

        olive = MockIngredient(id=str(uuid.uuid4()))
        recipe = MockRecipe(id=str(uuid.uuid4()))
        recipe.ingredients = [MockRecipeIngredient(ingredient=olive)]
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe=recipe, recipe_id=recipe.id,
        )
        # Two execute() calls: SELECT MealEvent, then SELECT ShoppingList
        # (empty → 404 path).
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[]),
        ]
        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_403_when_no_write_access_to_list(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        olive = MockIngredient(id=str(uuid.uuid4()))
        recipe = MockRecipe(id=str(uuid.uuid4()))
        recipe.ingredients = [MockRecipeIngredient(ingredient=olive)]
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe=recipe, recipe_id=recipe.id,
        )
        list_obj = MockShoppingList(id=str(uuid.uuid4()), owner_id=str(uuid.uuid4()))
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)
        mock_async_db.set_find_by(
            ShoppingListUser, None,
            shopping_list_id=list_obj.id, user_id=mock_user.id,
        )

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 403

    def test_re_tap_skips_already_added_items(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        olive = MockIngredient(id=str(uuid.uuid4()))
        recipe = MockRecipe(id=str(uuid.uuid4()))
        recipe.ingredients = [MockRecipeIngredient(ingredient=olive)]
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe=recipe, recipe_id=recipe.id,
        )
        existing_item = MockShoppingListItem(
            ingredient_id=olive.id, meal_event_id=event.id,
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=mock_user.id, items=[existing_item],
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["items_skipped"] == 1

    def test_404_when_recipe_relationship_unexpectedly_null(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe=None, recipe_id=str(uuid.uuid4()),
        )
        list_obj = MockShoppingList(id=str(uuid.uuid4()), owner_id=mock_user.id)
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 404

    def test_meal_event_re_tap_skips_already_added(self, client, mock_async_db, mock_user):
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        olive = MockIngredient(id=str(uuid.uuid4()))
        r = MockRecipe(id=str(uuid.uuid4()))
        r.recipe_book = None
        r.ingredients = [MockRecipeIngredient(ingredient=olive)]
        meal = MockMeal(
            id=str(uuid.uuid4()),
            components=[MockMealRecipe(recipe=r, order_index=0)],
        )
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe=None, recipe_id=None,
            meal_id=meal.id, meal=meal,
        )
        existing_item = MockShoppingListItem(
            ingredient_id=olive.id, meal_event_id=event.id,
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=mock_user.id, items=[existing_item],
        )
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        assert response.json()["items_skipped"] == 1

    def test_archived_or_orphan_recipe_ingredient_skipped(
        self, client, mock_async_db, mock_user
    ):
        """Archived RecipeIngredient + null-ingredient row must be skipped
        without crashing the per-event expansion."""
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        olive = MockIngredient(id=str(uuid.uuid4()))
        recipe = MockRecipe(id=str(uuid.uuid4()))
        archived_ri = MockRecipeIngredient(ingredient=olive)
        archived_ri.archived_at = "2026-01-01"
        orphan_ri = MockRecipeIngredient(ingredient=olive)
        orphan_ri.ingredient = None
        live_ri = MockRecipeIngredient(ingredient=olive)
        recipe.ingredients = [archived_ri, orphan_ri, live_ri]
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id,
            recipe=recipe, recipe_id=recipe.id,
        )
        list_obj = MockShoppingList(id=str(uuid.uuid4()), owner_id=mock_user.id)
        mock_async_db.set_find_by(MealEvent, event, id=event.id)
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[event]),
            MockExecuteResult(items=[list_obj]),
        ]
        mock_async_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meal-events/{event.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        # Only the live row contributes.
        assert response.json()["items_added"] == 1
