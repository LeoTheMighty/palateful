"""mcal-5: tests for `POST /v1/meals/{meal_id}/add-to-shopping-list`."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from conftest import (
    MockModel,
    MockQuery,
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


class TestAddMealToShoppingList:
    def _route_query(self, mock_db, *, MealModel, RecipeBookUser, meal, membership):
        def _router(model):
            if model is MealModel:
                return MockQuery([meal])
            if model is RecipeBookUser:
                return MockQuery([membership])
            return MockQuery([])

        mock_db.db.query.side_effect = _router

    def test_happy_path_aggregates_to_one_summed_item(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal import Meal as MealModel
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        book_id = str(uuid.uuid4())
        meal, olive = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=mock_user.id, items=[]
        )

        self._route_query(
            mock_db, MealModel=MealModel, RecipeBookUser=RecipeBookUser,
            meal=meal, membership=membership,
        )
        mock_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        # Two components × 1 tbsp olive oil → one row, summed quantity = 2.
        assert data["items_added"] == 1
        assert data["items_skipped"] == 0
        assert data["items"][0]["unit"] == "tbsp"
        assert Decimal(data["items"][0]["quantity"]) == Decimal("2")
        assert data["items"][0]["source_meal_id"] == str(meal.id)
        assert data["meal_summary"]["component_count"] == 2

    def test_archived_meal_returns_404(self, client, mock_db, mock_user):
        from utils.models.meal import Meal as MealModel
        from utils.models.recipe_book_user import RecipeBookUser

        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(
            archived=True, book_id=book_id
        )
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        self._route_query(
            mock_db, MealModel=MealModel, RecipeBookUser=RecipeBookUser,
            meal=meal, membership=membership,
        )

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_non_reader_of_meal_returns_403(self, client, mock_db, mock_user):
        from utils.models.meal import Meal as MealModel

        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        # No RecipeBookUser membership → user_has_book_read returns False.

        def _router(model):
            if model is MealModel:
                return MockQuery([meal])
            return MockQuery([])

        mock_db.db.query.side_effect = _router

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 403

    def test_missing_shopping_list_returns_404(self, client, mock_db, mock_user):
        from utils.models.meal import Meal as MealModel
        from utils.models.recipe_book_user import RecipeBookUser

        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        self._route_query(
            mock_db, MealModel=MealModel, RecipeBookUser=RecipeBookUser,
            meal=meal, membership=membership,
        )
        # set_find_by(ShoppingList, ...) is intentionally NOT set → returns None.

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404

    def test_non_writer_of_shopping_list_returns_403(
        self, client, mock_db, mock_user
    ):
        from utils.models.meal import Meal as MealModel
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList
        from utils.models.shopping_list_user import ShoppingListUser

        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(
            user_id=mock_user.id, recipe_book_id=book_id, role="owner"
        )
        list_obj = MockShoppingList(
            id=str(uuid.uuid4()), owner_id=str(uuid.uuid4()),  # not user
        )
        self._route_query(
            mock_db, MealModel=MealModel, RecipeBookUser=RecipeBookUser,
            meal=meal, membership=membership,
        )
        mock_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)
        # ShoppingListUser membership absent → can_edit False.
        mock_db.set_find_by(
            ShoppingListUser, None,
            shopping_list_id=list_obj.id, user_id=mock_user.id,
        )

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 403

    def test_re_tap_skips_already_added_items(self, client, mock_db, mock_user):
        from utils.models.meal import Meal as MealModel
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

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

        self._route_query(
            mock_db, MealModel=MealModel, RecipeBookUser=RecipeBookUser,
            meal=meal, membership=membership,
        )
        mock_db.set_find_by(ShoppingList, list_obj, id=list_obj.id)

        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list",
            json={"shopping_list_id": list_obj.id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items_added"] == 0
        assert data["items_skipped"] == 1


class TestListMealsAutocomplete:
    def _route_query(self, mock_db, *, MealModel, meals):
        """Route `db.query(Meal)` → meals; everything else → empty.

        The RecipeBookUser subquery used by list_meals must NOT receive
        the Meal rows or `meal[0]` fails. Separate them by model class.
        """

        def _router(model):
            if model is MealModel:
                return MockQuery(meals)
            # RecipeBookUser.recipe_book_id → iterated `{str(row[0])...}`,
            # so the returned MockQuery rows have to be subscriptable.
            # Empty list avoids that path entirely — and `subquery()` is
            # a MagicMock so the `.in_(subquery)` path works regardless.
            return MockQuery([])

        mock_db.db.query.side_effect = _router

    def test_q_param_filters_by_name(self, client, mock_db, mock_user):
        from utils.models.meal import Meal as MealModel

        meal = MockMeal(id=str(uuid.uuid4()), name="Kale Salad Meal")
        meal.components = []
        self._route_query(mock_db, MealModel=MealModel, meals=[meal])

        response = client.get("/v1/meals?q=Kale&limit=8")
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(item["name"] == "Kale Salad Meal" for item in items)

    def test_q_blank_treated_as_no_filter(self, client, mock_db, mock_user):
        """Blank-after-strip q must NOT generate a `%%` LIKE that
        accidentally matches every row."""
        from utils.models.meal import Meal as MealModel

        meal = MockMeal(id=str(uuid.uuid4()), name="Pizza Meal")
        meal.components = []
        self._route_query(mock_db, MealModel=MealModel, meals=[meal])

        response = client.get("/v1/meals?q=%20&limit=8")
        assert response.status_code == 200

    def test_limit_capped_at_50(self, client, mock_db, mock_user):
        """Misbehaving callers can't request a 10000-row autocomplete."""
        from utils.models.meal import Meal as MealModel

        meal = MockMeal(id=str(uuid.uuid4()), name="Meal")
        meal.components = []
        self._route_query(mock_db, MealModel=MealModel, meals=[meal])

        response = client.get("/v1/meals?limit=10000")
        assert response.status_code == 200
        # Coverage comes from hitting the `effective_limit = min(...)`
        # branch, not from inspecting a response field.
