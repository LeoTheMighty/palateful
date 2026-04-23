"""Tests for GET /v1/meals/public/{token} (msa-1).

Includes the **privacy invariant** assertion: the raw JSON response for a
shared Meal must NOT contain `recipe_id` / `order_index` / `book_id` on any
component entry. A stranger holding the public link should not be able to
probe private recipe UUIDs.

aam-10: handler converted to `AsyncEndpoint`. Tests configure
`mock_async_db.db.execute.side_effect` (2 execute calls per request:
the Meal load with selectinload + the RecipeBook lookup). The
`unauthed_client` fixture is updated in conftest to override the async
DB dep too.
"""

import json
from datetime import UTC, datetime

from conftest import (
    MockExecuteResult,
    MockModel,
    MockRecipe,
    MockRecipeBook,
)


class _MockMealRecipe(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "meal_id": "meal-1",
            "recipe_id": "r1",
            "order_index": 0,
            "recipe": None,
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


class _MockMeal(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "id": "meal-1",
            "name": "Kale Salad Meal",
            "description": "Summer lunch",
            "recipe_book_id": "book-1",
            "share_token": "tokenA" + "x" * 14,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _component(
    recipe_id="r1",
    name="Recipe",
    *,
    order=0,
    image_url=None,
    share_token=None,
    archived=False,
):
    recipe = MockRecipe(
        id=recipe_id,
        name=name,
        image_url=image_url,
        share_token=share_token,
        archived_at=datetime.now(UTC) if archived else None,
    )
    return _MockMealRecipe(
        recipe=recipe,
        recipe_id=recipe_id,
        order_index=order,
    )


class TestGetPublicMealByTokenHappy:
    """Valid token → 200 with the expected shape."""

    def test_happy_mixed_components(self, unauthed_client, mock_async_db):
        meal = _MockMeal(
            components=[
                _component("r1", "Lemon Dressing", share_token="recipetokenA" + "x" * 8),
                _component("r2", "Kale Salad", order=1, share_token=None),
            ]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[MockRecipeBook(id="book-1", name="Dinners")]),
        ]
        response = unauthed_client.get(f"/v1/meals/public/{meal.share_token}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "meal-1"
        assert data["name"] == "Kale Salad Meal"
        assert data["description"] == "Summer lunch"
        assert data["recipe_book_name"] == "Dinners"
        assert len(data["components"]) == 2
        assert data["components"][0]["name"] == "Lemon Dressing"
        assert data["components"][0]["has_public_token"] is True
        assert data["components"][0]["public_token"].startswith("recipetokenA")
        assert data["components"][1]["name"] == "Kale Salad"
        assert data["components"][1]["has_public_token"] is False
        assert data["components"][1]["public_token"] is None

    def test_empty_book_name_when_book_missing(self, unauthed_client, mock_async_db):
        meal = _MockMeal(components=[_component("r1", share_token="x" * 20)])
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[]),  # RecipeBook lookup returns nothing
        ]
        response = unauthed_client.get(f"/v1/meals/public/{meal.share_token}")
        assert response.status_code == 200
        assert response.json()["recipe_book_name"] == ""

    def test_orders_components_by_order_index(self, unauthed_client, mock_async_db):
        # Stored out of order to prove we re-sort by order_index.
        meal = _MockMeal(
            components=[
                _component("r2", "Second", order=1),
                _component("r1", "First", order=0),
            ]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[MockRecipeBook(id="book-1", name="Dinners")]),
        ]
        response = unauthed_client.get(f"/v1/meals/public/{meal.share_token}")
        assert response.status_code == 200
        names = [c["name"] for c in response.json()["components"]]
        assert names == ["First", "Second"]


class TestGetPublicMealByTokenArchived:
    """Archived meals + archived components are hidden from strangers."""

    def test_archived_meal_404(self, unauthed_client, mock_async_db):
        # The handler filters `archived_at IS NULL` inside the query, so a
        # DB with only an archived meal returns nothing → 404.
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = unauthed_client.get("/v1/meals/public/anytoken")
        assert response.status_code == 404

    def test_archived_component_omitted(self, unauthed_client, mock_async_db):
        meal = _MockMeal(
            components=[
                _component("r1", "Live", share_token="x" * 20),
                _component("r2", "Archived", order=1, archived=True),
            ]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[MockRecipeBook(id="book-1", name="Dinners")]),
        ]
        response = unauthed_client.get(f"/v1/meals/public/{meal.share_token}")
        assert response.status_code == 200
        components = response.json()["components"]
        assert len(components) == 1
        assert components[0]["name"] == "Live"

    def test_component_with_missing_recipe_omitted(self, unauthed_client, mock_async_db):
        bad = _MockMealRecipe(recipe_id="missing", recipe=None)
        meal = _MockMeal(
            components=[bad, _component("r1", "Survivor", share_token="x" * 20)]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[MockRecipeBook(id="book-1", name="Dinners")]),
        ]
        response = unauthed_client.get(f"/v1/meals/public/{meal.share_token}")
        assert response.status_code == 200
        components = response.json()["components"]
        assert len(components) == 1
        assert components[0]["name"] == "Survivor"


class TestGetPublicMealByTokenNotFound:
    """Invalid token → 404. Does not distinguish archived from invalid."""

    def test_invalid_token_404(self, unauthed_client, mock_async_db):
        mock_async_db.db.execute.return_value = MockExecuteResult(items=[])
        response = unauthed_client.get("/v1/meals/public/invalid-token-value")
        assert response.status_code == 404


class TestGetPublicMealPrivacyInvariant:
    """Privacy invariant: raw JSON must not expose `recipe_id` on components.

    This is the load-bearing test — if it fails, a stranger holding a
    shared-Meal link could enumerate private recipe UUIDs.
    """

    def test_no_recipe_id_key_in_components(self, unauthed_client, mock_async_db):
        meal = _MockMeal(
            components=[
                _component(
                    "super-secret-uuid",
                    "Private",
                    share_token=None,
                ),
                _component(
                    "public-uuid",
                    "Public",
                    order=1,
                    share_token="tokenB" + "x" * 14,
                ),
            ]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult(items=[meal]),
            MockExecuteResult(items=[MockRecipeBook(id="book-1", name="Dinners")]),
        ]
        response = unauthed_client.get(f"/v1/meals/public/{meal.share_token}")
        assert response.status_code == 200

        raw = response.text
        # Neither the private nor the public component's recipe_id should
        # appear anywhere in the wire payload.
        assert "super-secret-uuid" not in raw
        assert "public-uuid" not in raw

        # Belt-and-suspenders: walk the parsed components dict and make
        # sure there is no `recipe_id`, `order_index`, or `book_id` key.
        data = json.loads(raw)
        for component in data["components"]:
            assert "recipe_id" not in component
            assert "order_index" not in component
            assert "book_id" not in component
