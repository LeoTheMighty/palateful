"""md-1: UnifiedSearch meals tier tests.

Validates every branch of the scope-set parser + `_search_my_meals` tier
added in md-1:

* Scope parsing (`None`, `recipes`, `recipes,meals`, `meals`, bogus).
* Direct-name + component-name match paths.
* `matched_component` population / null-on-direct.
* Cross-book visibility of component matches.
* Pagination / limit hygiene.
* Zero-Meal user sees `my_meals=[]` (the zero-regression guarantee).

aam-17: `_search_my_meals` is now async on `UnifiedSearch(AsyncEndpoint)`.
Direct tier tests became `async def` + `await`; integration tests pre-configure
`mock_async_db.db.execute` instead of `mock_db.db.query`.
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


def _component(recipe_id, name, order=0, book_id="book-1", archived=False):
    book = MockRecipeBook(id=book_id, name="Dinners", archived_at=None)
    recipe = MockRecipe(
        id=recipe_id,
        name=name,
        recipe_book_id=book_id,
        recipe_book=book,
        image_url=f"https://cdn/{recipe_id}.jpg",
        archived_at=datetime.now(UTC) if archived else None,
    )
    return _MockMealRecipe(
        recipe_id=recipe_id, recipe=recipe, order_index=order
    )


def _make_endpoint(mock_async_db, mock_user):
    from api.v1.search.unified_search import UnifiedSearch

    return UnifiedSearch(user=mock_user, database=mock_async_db)


class TestResolveScope:
    """`_resolve_scope` — the scope-set parser."""

    def test_none_is_everything(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope(None) == (True, True, True)

    def test_empty_string_is_everything(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("") == (True, True, True)

    def test_recipes_only_drops_meals_and_users(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("recipes") == (True, False, False)

    def test_meals_only_drops_recipes_and_users(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("meals") == (False, True, False)

    def test_recipes_and_meals_is_everything(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("recipes,meals") == (True, True, True)

    def test_reversed_order_is_still_everything(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("meals,recipes") == (True, True, True)

    def test_whitespace_and_empty_segments_ignored(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope(" recipes , , meals") == (
            True, True, True,
        )

    def test_unknown_value_falls_back_to_everything(self):
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("bogus") == (True, True, True)

    def test_recipes_plus_unknown_falls_back_to_everything(self):
        """Anything beyond the three canonical sets is treated as a legacy
        caller — give them the full payload so they don't silently lose
        results after a scope typo. Explicitly NOT {"recipes"} semantics.
        """
        from api.v1.search.unified_search import UnifiedSearch

        assert UnifiedSearch._resolve_scope("recipes,events") == (
            True, True, True,
        )


class TestSearchMyMeals:
    """`_search_my_meals` tier — direct + component-name match paths."""

    async def test_zero_book_ids_short_circuits(self, mock_async_db, mock_user):
        endpoint = _make_endpoint(mock_async_db, mock_user)
        # book_ids=[] — no DB calls at all
        results = await endpoint._search_my_meals("dressing", 20, mock_user, [])
        assert results == []
        assert mock_async_db.db.execute.call_count == 0

    async def test_direct_name_match_populates_null_matched_component(
        self, mock_async_db, mock_user
    ):
        endpoint = _make_endpoint(mock_async_db, mock_user)
        meal = _MockMeal(
            name="Kale Salad Meal",
            components=[
                _component("r1", "Lemon Dressing"),
                _component("r2", "Kale Salad"),
            ],
        )
        calls = [0]

        def execute_side_effect(*_args, **_kwargs):
            calls[0] += 1
            if calls[0] == 1:
                return MockExecuteResult([(meal, "Dinners")])
            return MockExecuteResult([])

        mock_async_db.db.execute.side_effect = execute_side_effect

        results = await endpoint._search_my_meals(
            "Kale", 20, mock_user, ["book-1"]
        )

        assert len(results) == 1
        assert results[0].id == "meal-1"
        assert results[0].matched_component is None
        assert results[0].component_count == 2
        # top_component_image_urls hydrated from available components only
        assert len(results[0].top_component_image_urls) == 2

    async def test_component_name_match_populates_matched_component(
        self, mock_async_db, mock_user
    ):
        endpoint = _make_endpoint(mock_async_db, mock_user)
        meal = _MockMeal(
            name="Weeknight Combo",
            components=[
                _component("r-dressing", "Lemon Dressing", order=0),
                _component("r-salad", "Kale Salad", order=1),
            ],
        )
        calls = [0]

        def execute_side_effect(*_args, **_kwargs):
            calls[0] += 1
            if calls[0] == 1:
                # direct pass returns nothing
                return MockExecuteResult([])
            # component pass returns this meal
            return MockExecuteResult([(meal, "Dinners")])

        mock_async_db.db.execute.side_effect = execute_side_effect

        results = await endpoint._search_my_meals(
            "dressing", 20, mock_user, ["book-1"]
        )

        assert len(results) == 1
        assert results[0].matched_component is not None
        assert results[0].matched_component.name == "Lemon Dressing"
        assert results[0].matched_component.recipe_id == "r-dressing"

    async def test_direct_and_component_both_return_direct_first(
        self, mock_async_db, mock_user
    ):
        endpoint = _make_endpoint(mock_async_db, mock_user)
        direct_meal = _MockMeal(
            id="meal-direct",
            name="Dressing Plate",
            components=[_component("r1", "Olive Oil"), _component("r2", "Pepper")],
        )
        component_meal = _MockMeal(
            id="meal-comp",
            name="Kale Salad Meal",
            components=[
                _component("r3", "Lemon Dressing"),
                _component("r4", "Kale"),
            ],
        )
        calls = [0]

        def execute_side_effect(*_args, **_kwargs):
            calls[0] += 1
            if calls[0] == 1:
                return MockExecuteResult([(direct_meal, "A")])
            return MockExecuteResult([(component_meal, "B")])

        mock_async_db.db.execute.side_effect = execute_side_effect
        results = await endpoint._search_my_meals(
            "dressing", 20, mock_user, ["book-1"]
        )
        assert [r.id for r in results] == ["meal-direct", "meal-comp"]
        assert results[0].matched_component is None
        assert results[1].matched_component is not None

    async def test_direct_fills_limit_skips_component_query(
        self, mock_async_db, mock_user
    ):
        """When direct hits already fill the limit, we must NOT hit the DB
        a second time for the component query."""
        endpoint = _make_endpoint(mock_async_db, mock_user)
        meal = _MockMeal(components=[_component("r1", "A"), _component("r2", "B")])

        mock_async_db.db.execute.return_value = MockExecuteResult([(meal, "Dinners")])
        results = await endpoint._search_my_meals(
            "K", 1, mock_user, ["book-1"]
        )
        assert len(results) == 1
        assert mock_async_db.db.execute.call_count == 1

    async def test_archived_recipe_component_excluded_from_image_urls(
        self, mock_async_db, mock_user
    ):
        endpoint = _make_endpoint(mock_async_db, mock_user)
        meal = _MockMeal(
            components=[
                _component("r1", "Fresh", archived=False),
                _component("r2", "Old", archived=True),
            ],
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([(meal, "Dinners")]),
            MockExecuteResult([]),
        ]
        results = await endpoint._search_my_meals("Kale", 20, mock_user, ["book-1"])
        assert len(results[0].top_component_image_urls) == 1
        assert "r1" in results[0].top_component_image_urls[0]

    async def test_component_match_no_exact_component_name_hit_yields_null_matched(
        self, mock_async_db, mock_user
    ):
        """Defensive: if the DB returned a component-path row but no
        component names actually contain the query (eg. race between
        write + read), we surface the meal with `matched_component=None`
        rather than raising."""
        endpoint = _make_endpoint(mock_async_db, mock_user)
        meal = _MockMeal(
            components=[_component("r1", "Olive Oil"), _component("r2", "Pepper")],
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([]),
            MockExecuteResult([(meal, "Dinners")]),
        ]
        results = await endpoint._search_my_meals(
            "dressing", 20, mock_user, ["book-1"]
        )
        assert len(results) == 1
        assert results[0].matched_component is None

    async def test_top_image_urls_capped_at_four(self, mock_async_db, mock_user):
        endpoint = _make_endpoint(mock_async_db, mock_user)
        meal = _MockMeal(
            components=[
                _component(f"r{i}", f"Comp {i}", order=i) for i in range(6)
            ],
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([(meal, "B")]),
            MockExecuteResult([]),
        ]
        results = await endpoint._search_my_meals("x", 20, mock_user, ["book-1"])
        assert len(results[0].top_component_image_urls) == 4

    async def test_archived_book_component_excluded(self, mock_async_db, mock_user):
        """A component whose recipe lives in an ARCHIVED book must not leak
        its image_url into the response (defense-in-depth for the cross-book
        component visibility decision)."""
        endpoint = _make_endpoint(mock_async_db, mock_user)
        archived_book = MockRecipeBook(
            id="book-old", name="Old", archived_at=datetime.now(UTC)
        )
        recipe = MockRecipe(
            id="r1",
            name="Orphan",
            recipe_book_id="book-old",
            recipe_book=archived_book,
            image_url="https://cdn/r1.jpg",
        )
        comp = _MockMealRecipe(recipe_id="r1", recipe=recipe, order_index=0)
        meal = _MockMeal(
            components=[comp, _component("r2", "Fresh")]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([(meal, "B")]),
            MockExecuteResult([]),
        ]
        results = await endpoint._search_my_meals("K", 20, mock_user, ["book-1"])
        # archived-book component is filtered; only "Fresh" leaks its URL
        assert len(results[0].top_component_image_urls) == 1
        assert "r2" in results[0].top_component_image_urls[0]

    async def test_component_without_image_url_skipped(self, mock_async_db, mock_user):
        """A component with `image_url=None` is silently skipped — it does
        not count towards the 4-slot cap."""
        endpoint = _make_endpoint(mock_async_db, mock_user)
        book = MockRecipeBook(id="book-1", name="Dinners")
        recipe_no_img = MockRecipe(
            id="r1",
            name="Plain",
            recipe_book_id="book-1",
            recipe_book=book,
            image_url=None,
        )
        comp_no_img = _MockMealRecipe(
            recipe_id="r1", recipe=recipe_no_img, order_index=0
        )
        meal = _MockMeal(
            components=[comp_no_img, _component("r2", "WithImage")]
        )
        mock_async_db.db.execute.side_effect = [
            MockExecuteResult([(meal, "B")]),
            MockExecuteResult([]),
        ]
        results = await endpoint._search_my_meals("K", 20, mock_user, ["book-1"])
        assert len(results[0].top_component_image_urls) == 1
        assert "r2" in results[0].top_component_image_urls[0]


class TestUnifiedSearchScopeIntegration:
    """End-to-end scope behaviour through the FastAPI route."""

    def test_absent_scope_returns_empty_my_meals_key(
        self, client, mock_async_db, mock_user
    ):
        """Zero-regression: an empty DB still exposes `my_meals` in the
        response shape, so old widget-test fixtures see a consistent
        schema."""
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/search?q=pasta")
        assert resp.status_code == 200
        data = resp.json()
        assert "my_meals" in data
        assert data["my_meals"] == []

    def test_scope_recipes_excludes_my_meals(self, client, mock_async_db, mock_user):
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/search?q=pasta&scope=recipes")
        data = resp.json()
        assert data["my_meals"] == []
        assert data["users"] == []

    def test_scope_meals_returns_no_recipes_no_users(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/search?q=pasta&scope=meals")
        data = resp.json()
        assert data["my_recipes"] == []
        assert data["public_recipes"] == []
        assert data["users"] == []
        assert data["my_meals"] == []

    def test_scope_recipes_comma_meals_returns_everything(
        self, client, mock_async_db, mock_user
    ):
        mock_async_db.db.execute.return_value = MockExecuteResult([])
        resp = client.get("/v1/search?q=pasta&scope=recipes,meals")
        assert resp.status_code == 200
        data = resp.json()
        assert "my_meals" in data
        assert "my_recipes" in data
        assert "users" in data
