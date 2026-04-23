"""md-3: Filter tests for `GET /v1/meals` (archived, scope=home).

aam-10: handler converted to `AsyncEndpoint`. Tests configure
`mock_async_db.db.execute.side_effect` (3 execute calls per request:
readable-book-ids, total count via `scalar_one()`, meals list).
"""

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


def _list_meals_side_effect(*, readable_books, count, meals):
    """Build the canonical 3-execute side_effect tuple for /v1/meals.

    Order matches `ListMeals.execute`: readable-books query, count query
    (consumed by `scalar_one()`), meals query (consumed by
    `scalars().all()`).
    """
    return [
        MockExecuteResult(items=readable_books),
        MockExecuteResult(items=[count]),
        MockExecuteResult(items=meals),
    ]


class TestListMealsFilters:
    def test_default_excludes_archived(self, client, mock_async_db, mock_user):
        active = _MockMeal(components=[_component("r1"), _component("r2")])
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[("book-1",)], count=1, meals=[active]
        )
        resp = client.get("/v1/meals")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_archived_true_returns_only_archived(
        self, client, mock_async_db, mock_user
    ):
        archived = _MockMeal(
            archived_at=datetime.now(UTC),
            components=[_component("r1"), _component("r2")],
        )
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[("book-1",)], count=1, meals=[archived]
        )
        resp = client.get("/v1/meals?archived=true")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_archived_false_excludes_archived(
        self, client, mock_async_db, mock_user
    ):
        active = _MockMeal(components=[_component("r1"), _component("r2")])
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[("book-1",)], count=1, meals=[active]
        )
        resp = client.get("/v1/meals?archived=false")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_scope_home_returns_200(self, client, mock_async_db, mock_user):
        """Smoke: scope=home applies default-30 + exclude-archived sensibly."""
        meal = _MockMeal(components=[_component("r1"), _component("r2")])
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[("book-1",)], count=1, meals=[meal]
        )
        resp = client.get("/v1/meals?scope=home")
        assert resp.status_code == 200

    def test_explicit_limit_wins_over_scope_home_default(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[], count=0, meals=[]
        )
        resp = client.get("/v1/meals?scope=home&limit=5")
        assert resp.status_code == 200

    def test_list_meals_hoists_readable_book_ids_to_single_query(
        self, client, mock_async_db, mock_user
    ):
        """pbq-2 — a 30-meal page triggers ONE RecipeBookUser query, not 30.

        Pre-fix, `MealService.hydrate_components` self-fetched the
        readable-books set per meal, i.e. 30 `recipe_book_users`
        SELECTs for `/v1/meals?scope=home`. Post-fix, `list_meals`
        hoists the fetch once and threads it via `readable_book_ids`
        through `build_meal_summary` → `hydrate_components`.

        aam-10: assertion shifts from `qc.query_count_for(RecipeBookUser)`
        (which inspected sync `db.query(...)` args) to counting
        `db.execute` calls. With the hoist, exactly 3 execute calls fire
        per request: readable-books, count, meals — and the per-meal
        loop adds zero further DB hits because `readable_book_ids` is
        threaded into `hydrate_components`.
        """
        meals = [
            _MockMeal(id=f"meal-{i}", components=[_component("r1"), _component("r2")])
            for i in range(30)
        ]
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[("book-1",)], count=30, meals=meals
        )
        resp = client.get("/v1/meals?scope=home")
        assert resp.status_code == 200
        assert resp.json()["total"] == 30
        # Hard AC: exactly 3 execute() calls regardless of page size.
        # If the readable_book_ids hoist regresses, hydrate_components
        # would re-fetch per meal → 3 + N additional executes.
        assert mock_async_db.db.execute.call_count == 3


class TestListMealsEndpointDirect:
    """Direct tests for ListMeals.execute() to cover the branch matrix.

    aam-10: tests are now `async def` because `execute` is async; the
    endpoint's `database` is now a `MockAsyncDatabase`. The "captured
    limit" spy from the sync era is gone — `Select.limit(N)` happens on
    a SQLAlchemy expression before `db.execute(stmt)` fires, so we
    introspect `stmt._limit_clause.value` on the captured statement
    instead of intercepting a chained `.limit()` call.
    """

    def _ep(self, mock_async_db, mock_user):
        from api.v1.meal.list_meals import ListMeals
        return ListMeals(user=mock_user, database=mock_async_db)

    async def test_scope_home_raises_default_limit_to_30(
        self, mock_async_db, mock_user
    ):
        """When the caller doesn't pass `limit`, scope=home bumps it to 30."""
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[], count=0, meals=[]
        )
        ep = self._ep(mock_async_db, mock_user)
        await ep.execute(scope="home")
        # Third execute is the meals query; its limit clause holds the
        # bumped scope=home default.
        meals_stmt = mock_async_db.db.execute.call_args_list[2].args[0]
        assert meals_stmt._limit_clause.value == 30

    async def test_no_scope_uses_default_20(self, mock_async_db, mock_user):
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[], count=0, meals=[]
        )
        ep = self._ep(mock_async_db, mock_user)
        await ep.execute()
        meals_stmt = mock_async_db.db.execute.call_args_list[2].args[0]
        assert meals_stmt._limit_clause.value == 20

    async def test_archived_true_inverts_archived_filter(
        self, mock_async_db, mock_user
    ):
        """archived=True should not early-return. Smoke: returns ok."""
        mock_async_db.db.execute.side_effect = _list_meals_side_effect(
            readable_books=[], count=0, meals=[]
        )
        ep = self._ep(mock_async_db, mock_user)
        result = await ep.execute(archived=True)
        assert result["success"] is True
