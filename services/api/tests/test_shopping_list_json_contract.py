"""Wire contract: every cart response serializes quantities as JSON NUMBERS.

The shopping cart has been unusable since at least 2026-04. Opening a list
returned HTTP 200 and then crashed the app's parser:

    _TypeError: type 'String' is not a subtype of type 'num?' in type cast
    area=shopping.cart operation=loadList            (prod error_logs, service=client)

Pydantic v2 renders `Decimal` as a JSON *string*; the Dart model does
`json['quantity'] as num?`. Commit a5c84386 (2026-05-03) tried to fix this by
adding a Decimal→float serializer to `schemas/shopping_list.py::
ShoppingListItemResponse` — a class NO endpoint used. (That module was
dead in its entirety and is deleted with this fix, so a future fix cannot
land there again.) Its test exercised that
class directly and passed, while every endpoint kept building its own local
response model and kept sending strings. The fix shipped to prod and did
nothing.

So these tests deliberately assert on the thing the app actually parses: the
JSON body of the real route. A test on a schema class can go green while the
endpoint is still broken; a test on the response body cannot. Each test also
REQUIRES that at least one quantity was present — an item-less body passes
any type check vacuously, which is exactly how `test_get_shopping_list_success`
(`items=[]`) stayed green for the whole outage.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from conftest import MockShoppingList, MockShoppingListItem

QUANTITY_FIELDS = ("quantity", "already_have_quantity")


def _walk_quantities(node, path: str = "$"):
    """Yield (json_path, value) for every quantity field anywhere in the body."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in QUANTITY_FIELDS:
                yield f"{path}.{k}", v
            yield from _walk_quantities(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_quantities(v, f"{path}[{i}]")


def assert_quantities_are_json_numbers(body, where: str) -> None:
    """Every quantity in `body` is a JSON number or null — and at least one
    NON-NULL quantity exists, so the check cannot pass vacuously."""
    found = list(_walk_quantities(body))
    non_null = [(p, v) for p, v in found if v is not None]
    assert non_null, (
        f"{where}: no non-null quantity in the response body — the fixture must carry "
        f"an item with a quantity, or this test proves nothing (found: {found})"
    )
    bad = [
        (p, v)
        for p, v in found
        if v is not None and (not isinstance(v, int | float) or isinstance(v, bool))
    ]
    assert not bad, (
        f"{where}: quantities must be JSON numbers (the app does `as num?`), "
        f"got {[(p, type(v).__name__, v) for p, v in bad]}"
    )


def _list_with_item(mock_async_db, mock_user, list_id="test-list-id", item_id="test-item-id"):
    from utils.models.shopping_list import ShoppingList, ShoppingListItem

    item = MockShoppingListItem(
        id=item_id,
        shopping_list_id=list_id,
        name="Flour",
        quantity=Decimal("2.5"),
        already_have_quantity=Decimal("1"),
    )
    sl = MockShoppingList(
        id=list_id, owner_id=str(mock_user.id), items=[item], members=[], is_shared=False
    )
    mock_async_db.set_find_by(ShoppingList, sl, id=list_id)
    mock_async_db.set_find_by(ShoppingListItem, item, id=item_id, shopping_list_id=list_id)
    return sl, item


def _broadcast_payload(mock_broadcast) -> dict:
    """The item payload sent to other list members over the WebSocket."""
    mock_broadcast.assert_called_once()
    return mock_broadcast.call_args[0][2]


class TestGetShoppingList:
    """The MEASURED prod failure: GET /v1/shopping-lists/{list_id}."""

    def test_quantities_are_json_numbers(self, client, mock_db, mock_async_db, mock_user):
        _list_with_item(mock_async_db, mock_user)
        response = client.get("/v1/shopping-lists/test-list-id")
        assert response.status_code == 200
        assert_quantities_are_json_numbers(response.json(), "GET /v1/shopping-lists/{list_id}")
        # The value must survive the coercion, not just the type.
        assert response.json()["items"][0]["quantity"] == 2.5


class TestAddItem:
    """POST /v1/shopping-lists/{list_id}/items — the HTTP body AND the WS broadcast."""

    def test_response_and_broadcast_quantities_are_json_numbers(
        self, client, mock_db, mock_async_db, mock_user
    ):
        _list_with_item(mock_async_db, mock_user)
        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list", new_callable=AsyncMock
        ) as mock_broadcast:
            response = client.post(
                "/v1/shopping-lists/test-list-id/items",
                json={"name": "Sugar", "quantity": 2.5, "unit": "cup"},
            )
        assert response.status_code == 201
        assert_quantities_are_json_numbers(response.json(), "POST .../items (response)")
        # Other members' clients parse the broadcast with the same `as num?`.
        assert_quantities_are_json_numbers(_broadcast_payload(mock_broadcast), "POST .../items (WS broadcast)")


class TestUpdateItem:
    """PUT /v1/shopping-lists/{list_id}/items/{item_id} — HTTP body and WS broadcast."""

    def test_response_and_broadcast_quantities_are_json_numbers(
        self, client, mock_db, mock_async_db, mock_user
    ):
        _list_with_item(mock_async_db, mock_user)
        with patch(
            "routers.v1.shopping_list_router.broadcast_event_to_list", new_callable=AsyncMock
        ) as mock_broadcast:
            response = client.put(
                "/v1/shopping-lists/test-list-id/items/test-item-id",
                json={"quantity": 3.5},
            )
        assert response.status_code == 200
        assert_quantities_are_json_numbers(response.json(), "PUT .../items/{item_id} (response)")
        assert_quantities_are_json_numbers(
            _broadcast_payload(mock_broadcast), "PUT .../items/{item_id} (WS broadcast)"
        )


class TestCreateShoppingList:
    """POST /v1/shopping-lists with initial items."""

    def test_quantities_are_json_numbers(self, client, mock_db, mock_async_db, mock_user):
        response = client.post(
            "/v1/shopping-lists",
            json={"name": "Weekly", "items": [{"name": "Rice", "quantity": 2.5}]},
        )
        assert response.status_code == 201
        assert_quantities_are_json_numbers(response.json(), "POST /v1/shopping-lists")


class TestUpdateShoppingList:
    """PUT /v1/shopping-lists/{list_id} — returns the list with its items."""

    def test_quantities_are_json_numbers(self, client, mock_db, mock_async_db, mock_user):
        sl, _ = _list_with_item(mock_async_db, mock_user)
        # The update path reads these list settings; the shared mock omits them.
        # (Copied from test_shopping_list.py's update tests — which all use
        # `items=[]`, so none of them ever exercised a quantity.)
        sl.calendar_lookahead_days = 7
        sl.widget_color = None
        response = client.put("/v1/shopping-lists/test-list-id", json={"name": "Renamed"})
        assert response.status_code == 200
        assert_quantities_are_json_numbers(response.json(), "PUT /v1/shopping-lists/{list_id}")


class TestGetDeadlines:
    """GET /v1/shopping-lists/{list_id}/deadlines — items grouped by urgency."""

    def test_quantities_are_json_numbers(self, client, mock_db, mock_async_db, mock_user):
        from utils.models.shopping_list import ShoppingList

        item = MockShoppingListItem(
            id="i1", name="Urgent", is_checked=False,
            due_at=datetime.now() - timedelta(hours=1), due_reason=None,
            archived_at=None, category="produce", quantity=Decimal("2.5"),
            unit="each", priority=1, meal_event_id=None,
            assigned_to_user_id=None, notes=None, meal_event=None,
        )
        sl = MockShoppingList(id="test-list", owner_id=str(mock_user.id), items=[item])
        mock_async_db.set_find_by(ShoppingList, sl, id="test-list")
        response = client.get("/v1/shopping-lists/test-list/deadlines")
        assert response.status_code == 200
        assert_quantities_are_json_numbers(response.json(), "GET .../deadlines")


class TestPopulateFromRecipe:
    """POST /v1/shopping-lists/{list_id}/populate-from-recipe.

    (The existing success test checks name, unit, category, recipe_id and
    ingredient_id — every field except quantity.)"""

    def test_quantities_are_json_numbers(self, client, mock_db, mock_async_db, mock_user):
        import uuid

        from conftest import MockRecipe, MockRecipeBookUser
        from test_populate_from_recipe import make_recipe_ingredient
        from utils.models.recipe import Recipe
        from utils.models.recipe_book_user import RecipeBookUser
        from utils.models.shopping_list import ShoppingList

        list_id, recipe_id, ingredient_id = (str(uuid.uuid4()) for _ in range(3))
        recipe = MockRecipe(id=recipe_id, recipe_book_id=str(uuid.uuid4()))
        recipe.ingredients = [make_recipe_ingredient(ingredient_id, recipe_id)]
        sl = MockShoppingList(id=list_id, owner_id=str(mock_user.id), items=[])
        mock_async_db.set_find_by(Recipe, recipe, id=recipe_id)
        mock_async_db.set_find_by(
            RecipeBookUser,
            MockRecipeBookUser(),
            user_id=str(mock_user.id),
            recipe_book_id=recipe.recipe_book_id,
        )
        mock_async_db.set_find_by(ShoppingList, sl, id=list_id)
        response = client.post(
            f"/v1/shopping-lists/{list_id}/populate-from-recipe", json={"recipe_id": recipe_id}
        )
        assert response.status_code == 200
        assert_quantities_are_json_numbers(response.json(), "POST .../populate-from-recipe")


class TestGenerateFromMealEvent:
    """POST /v1/meal-events/{event_id}/shopping-list/generate."""

    def test_quantities_are_json_numbers(self, client, mock_db, mock_async_db, mock_user):
        from conftest import MockMealEvent, MockModel
        from utils.models.meal_event import MealEvent

        ingredient = MockModel(id="ing-1", canonical_name="Flour")
        recipe_ingredient = MockModel(
            id="ri-1", ingredient_id="ing-1", ingredient=ingredient,
            quantity_display=Decimal("2.5"), unit_display="cups", archived_at=None,
        )
        recipe = MockModel(id="recipe-1", name="Pancakes", ingredients=[recipe_ingredient])
        event = MockMealEvent(
            id="event-1", owner_id=str(mock_user.id), recipe=recipe,
            shopping_list=None, pantry_id=None, title="Sunday Brunch",
        )
        mock_async_db.set_find_by(MealEvent, event, id="event-1")
        response = client.post("/v1/meal-events/event-1/shopping-list/generate", json={})
        assert response.status_code == 201
        assert_quantities_are_json_numbers(response.json(), "POST .../shopping-list/generate")


class TestAddMealToShoppingList:
    """POST /v1/meals/{meal_id}/add-to-shopping-list.

    (The existing happy-path test asserts `Decimal(data["items"][0]["quantity"])
    == Decimal("1")` — wrapping the value in Decimal() ACCEPTS the string "1",
    so that test was written in a way that tolerated the broken wire format.)"""

    def test_quantities_are_json_numbers(self, client, mock_async_db, mock_user):
        import uuid

        from conftest import MockRecipeBookUser
        from test_add_meal_to_shopping_list import (
            MockShoppingList as MealMockShoppingList,
        )
        from test_add_meal_to_shopping_list import (
            _add_to_list_side_effect,
            _make_meal_with_two_olive_oil_components,
        )

        book_id = str(uuid.uuid4())
        meal, _ = _make_meal_with_two_olive_oil_components(book_id=book_id)
        membership = MockRecipeBookUser(user_id=mock_user.id, recipe_book_id=book_id, role="owner")
        list_obj = MealMockShoppingList(id=str(uuid.uuid4()), owner_id=mock_user.id, items=[])
        mock_async_db.db.execute.side_effect = _add_to_list_side_effect(
            meal=meal, membership=membership, shopping_list=list_obj
        )
        response = client.post(
            f"/v1/meals/{meal.id}/add-to-shopping-list", json={"shopping_list_id": list_obj.id}
        )
        assert response.status_code == 200
        assert_quantities_are_json_numbers(response.json(), "POST /v1/meals/{meal_id}/add-to-shopping-list")


class TestAddMealEventToShoppingList:
    """POST /v1/meal-events/{event_id}/add-to-shopping-list."""

    def test_quantities_are_json_numbers(self, client, mock_async_db, mock_user):
        import uuid

        from conftest import MockExecuteResult, MockMealEvent, MockRecipe
        from test_add_meal_event_to_shopping_list import (
            MockIngredient as EvMockIngredient,
        )
        from test_add_meal_event_to_shopping_list import (
            MockRecipeIngredient as EvMockRecipeIngredient,
        )
        from test_add_meal_event_to_shopping_list import (
            MockShoppingList as EvMockShoppingList,
        )
        from utils.models.meal_event import MealEvent
        from utils.models.shopping_list import ShoppingList

        olive = EvMockIngredient(id=str(uuid.uuid4()))
        recipe = MockRecipe(id=str(uuid.uuid4()), name="Pizza")
        recipe.ingredients = [EvMockRecipeIngredient(ingredient=olive)]  # quantity_display=1
        event = MockMealEvent(
            id=str(uuid.uuid4()), owner_id=mock_user.id, recipe=recipe,
            recipe_id=recipe.id, meal_id=None, meal=None,
        )
        list_obj = EvMockShoppingList(id=str(uuid.uuid4()), owner_id=mock_user.id)
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
        assert_quantities_are_json_numbers(
            response.json(), "POST /v1/meal-events/{event_id}/add-to-shopping-list"
        )
