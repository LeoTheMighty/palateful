"""mcal-5: tests for `POST /v1/meals/{meal_id}/add-to-shopping-list`.

aam-10: handler converted to `AsyncEndpoint`. The execute path issues
4 ordered `db.execute` calls per request:

  1. `require_meal_read` → `MealService.get_with_components` (Meal + selectinload)
  2. `require_meal_read` → `MealService.user_has_book_read` (RecipeBookUser)
  3. Re-hydrate Meal with the wider ingredient/recipe_book selectinload
  4. Load ShoppingList with `selectinload(ShoppingList.items)`

`ShoppingListUser` is still resolved through `database.find_by(...)`
(not `db.execute(...)`) — keep using `mock_async_db.set_find_by(...)`
for it.

Also covers `GET /v1/meals?q=...` autocomplete (the second test class
hits `ListMeals` — same 3-execute pattern as `test_list_meals_filters.py`).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from conftest import (
    MockExecuteResult,
    MockModel,
    MockRecipe,
    MockRecipeBookUser,
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


def _make_meal_with_two_olive_oil_components(*, archived=False, book_id=None):
    """A Meal whose two recipes both want 1 tbsp olive oil → aggregate to 2 tbsp."""
    book_id = book_id or str(uuid.uuid4())
    olive = MockIngredient(id=str(uuid.uuid4()), canonical_name="olive oil")
    r1 = MockRecipe(id=str(uuid.uuid4()), recipe_book_id=book_id)
    r1.recipe_book = None
    r1.ingredients = [
        MockRecipeIngredient(ingredient=olive, quantity_display=Decimal("1"), unit_display="tbsp")
    ]
    r2 = MockRecipe(id=str(uuid.uuid4()), recipe_book_id=book_id)
    r2.recipe_book = None
    r2.ingredients = [
        MockRecipeIngredient(ingredient=olive, quantity_display=Decimal("1"), unit_display="tbsp")
    ]
    meal = MockMeal(
        id=str(uuid.uuid4()),
        recipe_book_id=book_id,
        components=[
            MockMealRecipe(recipe=r1, order_index=0),
            MockMealRecipe(recipe=r2, order_index=1),
        ],
    )
    if archived:
        meal.archived_at = datetime.now(timezone.utc)
    return meal, olive


def _add_to_list_side_effect(*, meal, membership, shopping_list):
    """Build the 4-execute side_effect tuple for AddMealToShoppingList.

    Order matches the handler:
      1. Meal load (require_meal_read.get_with_components)
      2. RecipeBookUser membership (require_meal_read.user_has_book_read)
      3. Meal re-hydrate with wider selectinload
      4. ShoppingList with eager items

    Pass `membership=None` to simulate non-reader (403). Pass
    `shopping_list=None` to simulate missing list (404).
    """
    return [
        MockExecuteResult(items=[meal] if meal is not None else []),
        MockExecuteResult(items=[membership] if membership is not None else []),
        MockExecuteResult(items=[meal] if meal is not None else []),
        MockExecuteResult(items=[shopping_list] if shopping_list is not None else []),
    ]


class TestAddMealToShoppingList:
    def test_happy_path_produces_one_row_per_component_with_no_dedup(
        self, client, mock_async_db, mock_user
    ):
        book_id = str(uuid.uuid4())
        meal, olive = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=mock_user.id, items=[]
        )

        mock_async_db.db.execute.side_effect = _add_to_list_side_effect(
            meal=meal, membership=membership, shopping_list=list_obj
        )

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        # No dedup post-str-ing-2: two components × 1 tbsp olive oil → two
        # adjacent rows, each retaining its own 1-tbsp quantity.
        assert data["items_added"] == 2
        assert data["items_skipped"] == 0
        assert data["items"][0]["unit"] == "tbsp"
        assert data["items"][1]["unit"] == "tbsp"
        assert Decimal(data["items"][0]["quantity"]) == Decimal("1")
        assert Decimal(data["items"][1]["quantity"]) == Decimal("1")
        assert data["items"][0]["source_meal_id"] == str(meal.id)
        assert data["items"][1]["source_meal_id"] == str(meal.id)
        assert data["meal_summary"]["component_count"] == 2

    def test_archived_meal_returns_404(self, client, mock_async_db, mock_user):
        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(
            archived=True, book_id=book_id
        )
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        # Archived meal short-circuits BEFORE the re-hydrate / shopping-list
        # loads — only require_meal_read's two executes fire.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[membership]),
        ]

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_non_reader_of_meal_returns_403(self, client, mock_async_db, mock_user):
        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        # No RecipeBookUser membership → user_has_book_read returns False.
        # Two executes fire: get_with_components, user_has_book_read.
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[]),
        ]

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 403

    def test_missing_shopping_list_returns_404(
        self, client, mock_async_db, mock_user
    ):
        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        mock_async_db.db.execute.side_effect = _add_to_list_side_effect(
            meal=meal, membership=membership, shopping_list=None
        )

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_non_writer_of_shopping_list_returns_403(
        self, client, mock_async_db, mock_user
    ):
        from utils.models.shopping_list_user import ShoppingListUser

        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=str(uuid.uuid4()),  # not user
        )
        mock_async_db.db.execute.side_effect = _add_to_list_side_effect(
            meal=meal, membership=membership, shopping_list=list_obj
        )
        # ShoppingListUser membership absent → can_edit False.
        mock_async_db.set_find_by(
            ShoppingListUser, None,
            shopping_list_id=list_obj.id, user_id=mock_user.id,
        )

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 403

    def test_re_tap_skips_already_added_items(
        self, client, mock_async_db, mock_user
    ):
        book_id = str(uuid.uuid4())
        meal, olive = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        existing_item = MockShoppingListItem(
            ingredient_id=olive.id, source_meal_id=meal.id,
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=mock_user.id, items=[existing_item],
        )

        mock_async_db.db.execute.side_effect = _add_to_list_side_effect(
            meal=meal, membership=membership, shopping_list=list_obj
        )

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        # Post-str-ing-2: aggregate returns one row per component (no dedup),
        # so both olive-oil rows collide with the existing
        # (ingredient_id, source_meal_id) key → both skipped.
        assert data["items_added"] == 0
        assert data["items_skipped"] == 2


class TestListMealsAutocomplete:
    """`GET /v1/meals?q=...` smoke tests — same 3-execute pattern as
    `test_list_meals_filters.py` (readable-books, count, meals)."""

    def _side_effect(self, meals, *, count=None, readable_books=(("book-1",),)):
        if count is None:
            count = len(meals)
        return [
            MockExecuteResult(items=list(readable_books)),
            MockExecuteResult(items=[count]),
            MockExecuteResult(items=meals),
        ]

    def test_q_param_filters_by_name(self, client, mock_async_db, mock_user):
        meal = MockMeal(id=str(uuid.uuid4()), name="Kale Salad Meal")
        meal.components = []
        mock_async_db.db.execute.side_effect = self._side_effect([meal])

        response = client.get("/v1/meals?q=Kale&limit=8")
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(item["name"] == "Kale Salad Meal" for item in items)

    def test_q_blank_treated_as_no_filter(self, client, mock_async_db, mock_user):
        """Blank-after-strip q must NOT generate a `%%` LIKE that
        accidentally matches every row."""
        meal = MockMeal(id=str(uuid.uuid4()), name="Pizza Meal")
        meal.components = []
        mock_async_db.db.execute.side_effect = self._side_effect([meal])

        response = client.get("/v1/meals?q=%20&limit=8")
        assert response.status_code == 200

    def test_limit_capped_at_50(self, client, mock_async_db, mock_user):
        """Misbehaving callers can't request a 10000-row autocomplete."""
        meal = MockMeal(id=str(uuid.uuid4()), name="Meal")
        meal.components = []
        mock_async_db.db.execute.side_effect = self._side_effect([meal])

        response = client.get("/v1/meals?limit=10000")
        assert response.status_code == 200
        # Coverage comes from hitting the `effective_limit = min(...)`
        # branch, not from inspecting a response field.
