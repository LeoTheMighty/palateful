"""Tests for Meal HTTP endpoints (mcv-2 scope).

mcv-2 handlers covered:
  POST   /v1/recipe-books/{book_id}/meals     (CreateMeal)
  GET    /v1/meals/{meal_id}                   (GetMeal)
  GET    /v1/meals                             (ListMeals)
  GET    /v1/recipe-books/{book_id}/meals      (ListMealsInBook)
  PATCH  /v1/meals/{meal_id}                   (UpdateMeal)
  POST   /v1/meals/{meal_id}/archive           (ArchiveMeal)
  POST   /v1/meals/{meal_id}/restore           (RestoreMeal)

mcv-3 handlers (component add/remove/reorder, favorite) land under a
dedicated test file when mcv-3 ships.
"""

from datetime import UTC, datetime

from conftest import (
    MockModel,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)


class _MockMealRecipe(MockModel):
    def __init__(self, **kwargs):
        defaults = {
            "meal_id": "meal-1",
            "recipe_id": "recipe-1",
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
            "description": None,
            "recipe_book_id": "book-1",
            "share_token": None,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _owner():
    return MockRecipeBookUser(role="owner")


def _build_component(recipe_id="r1", name="R", order=0, book_id="book-1"):
    book = MockRecipeBook(id=book_id, name="Dinners")
    recipe = MockRecipe(
        id=recipe_id,
        name=name,
        recipe_book_id=book_id,
        recipe_book=book,
    )
    return _MockMealRecipe(
        recipe=recipe, recipe_id=recipe_id, order_index=order
    )


class TestCreateMeal:
    """POST /v1/recipe-books/{book_id}/meals."""

    def test_happy(self, client, mock_db, mock_user):
        meal = _MockMeal(components=[_build_component("r1"), _build_component("r2", "R2", 1)])
        # Query order:
        # 1. require_book_write → user_has_book_write → RecipeBookUser query (owner)
        # 2. create_with_components → _ensure_components_readable → Recipe.in_ query
        # 3. _readable_book_ids query
        # 4. get_with_components → Meal query (re-fetch)
        # 5. build_meal_response → hydrate_components → _readable_book_ids
        # 6. build_meal_response → is_favorited → MealFavorite query
        mock_db.db.query.side_effect = [
            MockQuery([_owner()]),
            MockQuery(
                [
                    MockRecipe(
                        id="r1",
                        recipe_book_id="book-1",
                        recipe_book=MockRecipeBook(id="book-1"),
                    ),
                    MockRecipe(
                        id="r2",
                        recipe_book_id="book-1",
                        recipe_book=MockRecipeBook(id="book-1"),
                    ),
                ]
            ),
            MockQuery([("book-1",)]),
            MockQuery([meal]),
            MockQuery([("book-1",)]),
            MockQuery([]),
        ]

        response = client.post(
            "/v1/recipe-books/book-1/meals",
            json={
                "name": "Kale Salad Meal",
                "description": "tonight",
                "component_recipe_ids": ["r1", "r2"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Kale Salad Meal"
        assert data["recipe_book_id"] == "book-1"
        assert len(data["components"]) == 2

    def test_rejects_fewer_than_two(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recipe-books/book-1/meals",
            json={"name": "X", "component_recipe_ids": ["r1"]},
        )
        assert response.status_code == 422

    def test_rejects_duplicate_components(self, client, mock_db, mock_user):
        response = client.post(
            "/v1/recipe-books/book-1/meals",
            json={"name": "X", "component_recipe_ids": ["r1", "r1"]},
        )
        assert response.status_code == 422

    def test_rejects_non_book_member(self, client, mock_db, mock_user):
        # user_has_book_write returns False → empty membership query
        mock_db.db.query.return_value = MockQuery([])
        response = client.post(
            "/v1/recipe-books/book-1/meals",
            json={"name": "X", "component_recipe_ids": ["r1", "r2"]},
        )
        assert response.status_code == 403

    def test_rejects_viewer(self, client, mock_db, mock_user):
        """Viewer has read but not write — 403."""
        mock_db.db.query.return_value = MockQuery(
            [MockRecipeBookUser(role="viewer")]
        )
        response = client.post(
            "/v1/recipe-books/book-1/meals",
            json={"name": "X", "component_recipe_ids": ["r1", "r2"]},
        )
        assert response.status_code == 403

    def test_rejects_unreadable_component(self, client, mock_db, mock_user):
        # Owner of book, but referenced recipe is in a book the user can't read
        mock_db.db.query.side_effect = [
            MockQuery([_owner()]),
            MockQuery(
                [
                    MockRecipe(
                        id="r1",
                        recipe_book_id="book-private",
                        recipe_book=MockRecipeBook(id="book-private"),
                    ),
                    MockRecipe(
                        id="r2",
                        recipe_book_id="book-private",
                        recipe_book=MockRecipeBook(id="book-private"),
                    ),
                ]
            ),
            MockQuery([("book-1",)]),  # Only book-1 is readable
        ]
        response = client.post(
            "/v1/recipe-books/book-1/meals",
            json={"name": "X", "component_recipe_ids": ["r1", "r2"]},
        )
        assert response.status_code == 404


class TestGetMeal:
    """GET /v1/meals/{meal_id}."""

    def test_happy(self, client, mock_db, mock_user):
        meal = _MockMeal(
            components=[_build_component("r1"), _build_component("r2", "R2", 1)]
        )
        mock_db.db.query.side_effect = [
            MockQuery([meal]),          # get_with_components
            MockQuery([_owner()]),      # user_has_book_read
            MockQuery([("book-1",)]),   # hydrate_components → _readable_book_ids
            MockQuery([]),              # is_favorited → MealFavorite lookup
        ]
        response = client.get("/v1/meals/meal-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "meal-1"
        assert len(data["components"]) == 2

    def test_not_found(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/meals/nope")
        assert response.status_code == 404

    def test_non_member_403(self, client, mock_db, mock_user):
        meal = _MockMeal()
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([]),  # not a book member
        ]
        response = client.get("/v1/meals/meal-1")
        assert response.status_code == 403

    def test_reader_can_see(self, client, mock_db, mock_user):
        """A 'viewer' role on the book can still GET the meal."""
        meal = _MockMeal(components=[_build_component("r1"), _build_component("r2", "R2", 1)])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → MealFavorite
        ]
        response = client.get("/v1/meals/meal-1")
        assert response.status_code == 200

    def test_component_archived_marks_unavailable(self, client, mock_db, mock_user):
        comp = _build_component("r1")
        comp.recipe.archived_at = datetime.now(UTC)
        meal = _MockMeal(components=[comp, _build_component("r2", "R2", 1)])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → MealFavorite
        ]
        response = client.get("/v1/meals/meal-1")
        assert response.status_code == 200
        data = response.json()
        assert any(c["available"] is False for c in data["components"])

    def test_is_favorite_true_when_favorited(self, client, mock_db, mock_user):
        meal = _MockMeal(
            components=[_build_component("r1"), _build_component("r2", "R2", 1)]
        )
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([("book-1",)]),
            MockQuery(["favorite-row"]),  # is_favorited → returns truthy row
        ]
        response = client.get("/v1/meals/meal-1")
        assert response.status_code == 200
        assert response.json()["is_favorite"] is True

    def test_is_favorite_false_when_not_favorited(self, client, mock_db, mock_user):
        meal = _MockMeal(
            components=[_build_component("r1"), _build_component("r2", "R2", 1)]
        )
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → no row
        ]
        response = client.get("/v1/meals/meal-1")
        assert response.status_code == 200
        assert response.json()["is_favorite"] is False


class TestListMealsInBook:
    """GET /v1/recipe-books/{book_id}/meals."""

    def test_happy(self, client, mock_db, mock_user):
        meal = _MockMeal(components=[_build_component("r1"), _build_component("r2", "R2", 1)])
        # Queries: 1) membership  2) Meal query (count+all share it)  3) hydrate per meal
        mock_db.db.query.side_effect = [
            MockQuery([_owner()]),
            MockQuery([meal]),
            MockQuery([("book-1",)]),
        ]
        response = client.get("/v1/recipe-books/book-1/meals")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["component_count"] == 2
        # hmp-1: component_recipe_ids emitted in hydration order so
        # home can run the client-side join against loaded recipes.
        assert data["items"][0]["component_recipe_ids"] == ["r1", "r2"]

    def test_non_member_403(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.get("/v1/recipe-books/book-1/meals")
        assert response.status_code == 403

    def test_include_archived_toggle(self, client, mock_db, mock_user):
        archived = _MockMeal(archived_at=datetime.now(UTC))
        mock_db.db.query.side_effect = [
            MockQuery([_owner()]),
            MockQuery([archived]),
            MockQuery([("book-1",)]),
        ]
        response = client.get(
            "/v1/recipe-books/book-1/meals?include_archived=true"
        )
        assert response.status_code == 200


class TestListMeals:
    """GET /v1/meals."""

    def test_happy(self, client, mock_db, mock_user):
        meal = _MockMeal(components=[_build_component("r1"), _build_component("r2", "R2", 1)])
        # 1) readable_books subquery  2) Meal (count+all)  3) hydrate per meal
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([meal]),
            MockQuery([("book-1",)]),
        ]
        response = client.get("/v1/meals")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_include_archived_empty(self, client, mock_db, mock_user):
        # No meals returned → no hydrate call; just 2 queries.
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([]),
        ]
        response = client.get("/v1/meals?include_archived=true")
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestUpdateMeal:
    """PATCH /v1/meals/{meal_id}."""

    def test_update_name(self, client, mock_db, mock_user):
        meal = _MockMeal(components=[_build_component("r1"), _build_component("r2", "R2", 1)])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → MealFavorite
        ]
        response = client.patch(
            "/v1/meals/meal-1", json={"name": "Renamed"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    def test_update_description_only(self, client, mock_db, mock_user):
        meal = _MockMeal(components=[_build_component("r1"), _build_component("r2", "R2", 1)])
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
            MockQuery([("book-1",)]),
            MockQuery([]),  # is_favorited → MealFavorite
        ]
        response = client.patch(
            "/v1/meals/meal-1", json={"description": "New desc"}
        )
        assert response.status_code == 200
        assert response.json()["description"] == "New desc"

    def test_non_writer_403(self, client, mock_db, mock_user):
        meal = _MockMeal()
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
        ]
        response = client.patch(
            "/v1/meals/meal-1", json={"name": "x"}
        )
        assert response.status_code == 403

    def test_not_found(self, client, mock_db, mock_user):
        mock_db.db.query.return_value = MockQuery([])
        response = client.patch(
            "/v1/meals/nope", json={"name": "x"}
        )
        assert response.status_code == 404


class TestArchiveMeal:
    """POST /v1/meals/{meal_id}/archive."""

    def test_happy_archives_and_writes_audit(self, client, mock_db, mock_user):
        meal = _MockMeal(archived_at=None)
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/archive")
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert meal.archived_at is not None

    def test_already_archived_400(self, client, mock_db, mock_user):
        meal = _MockMeal(archived_at=datetime.now(UTC))
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/archive")
        assert response.status_code == 400

    def test_non_writer_403(self, client, mock_db, mock_user):
        meal = _MockMeal()
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
        ]
        response = client.post("/v1/meals/meal-1/archive")
        assert response.status_code == 403


class TestRestoreMeal:
    """POST /v1/meals/{meal_id}/restore."""

    def test_happy(self, client, mock_db, mock_user):
        meal = _MockMeal(archived_at=datetime.now(UTC))
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/restore")
        assert response.status_code == 200
        assert meal.archived_at is None

    def test_not_archived_400(self, client, mock_db, mock_user):
        meal = _MockMeal(archived_at=None)
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([_owner()]),
        ]
        response = client.post("/v1/meals/meal-1/restore")
        assert response.status_code == 400

    def test_non_writer_403(self, client, mock_db, mock_user):
        meal = _MockMeal(archived_at=datetime.now(UTC))
        mock_db.db.query.side_effect = [
            MockQuery([meal]),
            MockQuery([MockRecipeBookUser(role="viewer")]),
        ]
        response = client.post("/v1/meals/meal-1/restore")
        assert response.status_code == 403
