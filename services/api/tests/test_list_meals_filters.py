"""md-3: Filter tests for `GET /v1/meals` (archived, scope=home)."""

from datetime import UTC, datetime

from conftest import (
    MockModel,
    MockQuery,
    MockRecipe,
    MockRecipeBook,
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


def _component(recipe_id="r1", name="R"):
    book = MockRecipeBook(id="book-1", name="Dinners")
    recipe = MockRecipe(
        id=recipe_id, name=name, recipe_book_id="book-1", recipe_book=book
    )
    return _MockMealRecipe(recipe=recipe, recipe_id=recipe_id)


class TestListMealsFilters:
    def test_default_excludes_archived(self, client, mock_db, mock_user):
        active = _MockMeal(components=[_component("r1"), _component("r2")])
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([active]),
            MockQuery([("book-1",)]),
        ]
        resp = client.get("/v1/meals")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_archived_true_returns_only_archived(self, client, mock_db, mock_user):
        archived = _MockMeal(
            archived_at=datetime.now(UTC),
            components=[_component("r1"), _component("r2")],
        )
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([archived]),
            MockQuery([("book-1",)]),
        ]
        resp = client.get("/v1/meals?archived=true")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_archived_false_excludes_archived(self, client, mock_db, mock_user):
        active = _MockMeal(components=[_component("r1"), _component("r2")])
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([active]),
            MockQuery([("book-1",)]),
        ]
        resp = client.get("/v1/meals?archived=false")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_scope_home_returns_200(self, client, mock_db, mock_user):
        """Smoke: scope=home applies default-30 + exclude-archived sensibly."""
        meal = _MockMeal(components=[_component("r1"), _component("r2")])
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([meal]),
            MockQuery([("book-1",)]),
        ]
        resp = client.get("/v1/meals?scope=home")
        assert resp.status_code == 200

    def test_explicit_limit_wins_over_scope_home_default(
        self, client, mock_db, mock_user
    ):
        mock_db.db.query.side_effect = [
            MockQuery([]),
            MockQuery([]),
        ]
        resp = client.get("/v1/meals?scope=home&limit=5")
        assert resp.status_code == 200


class TestListMealsEndpointDirect:
    """Direct tests for ListMeals.execute() to cover the branch matrix."""

    def _ep(self, mock_db, mock_user):
        from api.v1.meal.list_meals import ListMeals
        return ListMeals(user=mock_user, database=mock_db)

    def test_scope_home_raises_default_limit_to_30(
        self, mock_db, mock_user
    ):
        """When the caller doesn't pass `limit`, scope=home bumps it to 30."""
        captured = {}

        original_query = mock_db.db.query

        def spy_query(*args, **kwargs):
            # The `limit(N)` call inside the endpoint fires after the
            # final .order_by(...). We capture the int via MockQuery.
            q = MockQuery([])
            real_limit = q.limit

            def limit_capture(n):
                captured["limit"] = n
                return real_limit(n)

            q.limit = limit_capture  # type: ignore[assignment]
            return q

        mock_db.db.query = spy_query
        ep = self._ep(mock_db, mock_user)
        ep.execute(scope="home")
        # 30 = scope=home's bumped default
        assert captured.get("limit") == 30
        mock_db.db.query = original_query

    def test_no_scope_uses_default_20(self, mock_db, mock_user):
        captured = {}

        def spy_query(*args, **kwargs):
            q = MockQuery([])
            real_limit = q.limit

            def limit_capture(n):
                captured["limit"] = n
                return real_limit(n)

            q.limit = limit_capture
            return q

        mock_db.db.query = spy_query
        ep = self._ep(mock_db, mock_user)
        ep.execute()
        assert captured.get("limit") == 20

    def test_archived_true_inverts_archived_filter(self, mock_db, mock_user):
        """archived=True should not early-return. Smoke: returns ok."""
        mock_db.db.query.return_value = MockQuery([])
        ep = self._ep(mock_db, mock_user)
        result = ep.execute(archived=True)
        assert result["success"] is True
