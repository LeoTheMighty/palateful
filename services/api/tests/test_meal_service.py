"""Unit tests for MealService (mcv-2 scope).

Exercises the service layer directly with mock sessions so every branch
of hydrate_components / create_with_components / archive / restore is
covered without having to route everything through the HTTP layer.

mcv-3 adds add_component / remove_component / reorder_components /
set_favorite methods; those get their own tests when mcv-3 lands.

aam-10: `MealService` methods are `async`. `_build_service` now returns
a MagicMock session whose write surface (`execute`, `flush`, `refresh`,
`delete`) is `AsyncMock` so handler code can `await` each call.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import (
    MockExecuteResult,
    MockModel,
    MockRecipe,
    MockRecipeBook,
    MockRecipeBookUser,
)

from utils.models.meal import Meal
from utils.services.meal_service import (
    ComponentUnreadableError,
    MealService,
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
            "name": "Kale Salad Meal",
            "description": None,
            "recipe_book_id": "book-1",
            "share_token": None,
            "components": [],
        }
        defaults.update(kwargs)
        super().__init__(**defaults)


def _build_service():
    """Build a MealService backed by a MagicMock async session."""
    session = MagicMock()
    session.execute = AsyncMock(return_value=MockExecuteResult())
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    service = MealService(session)
    return service, session


class TestHydrateComponents:
    async def test_all_available(self):
        service, session = _build_service()
        book = MockRecipeBook(id="book-1", name="Dinners")
        r1 = MockRecipe(
            id="recipe-1",
            name="Kale Salad",
            image_url="https://img/kale.jpg",
            prep_time=10,
            cook_time=0,
            recipe_book_id="book-1",
            recipe_book=book,
        )
        r2 = MockRecipe(
            id="recipe-2",
            name="Lemon Dressing",
            image_url=None,
            prep_time=5,
            cook_time=0,
            recipe_book_id="book-1",
            recipe_book=book,
        )
        meal = _MockMeal(
            components=[
                _MockMealRecipe(recipe=r1, recipe_id=r1.id, order_index=0),
                _MockMealRecipe(recipe=r2, recipe_id=r2.id, order_index=1),
            ]
        )
        # _readable_book_ids returns [("book-1",)]
        session.execute.return_value = MockExecuteResult(items=[("book-1",)])

        hydrations = await service.hydrate_components(meal, user_id="user-1")
        assert len(hydrations) == 2
        assert all(h.available for h in hydrations)
        assert hydrations[0].name == "Kale Salad"
        assert hydrations[0].book_name == "Dinners"
        assert hydrations[1].image_url is None
        assert hydrations[0].last_known_name is None

    async def test_archived_recipe_is_unavailable(self):
        service, session = _build_service()
        book = MockRecipeBook(id="book-1", name="Dinners")
        archived = MockRecipe(
            id="recipe-1",
            name="Archived Recipe",
            recipe_book_id="book-1",
            recipe_book=book,
            archived_at=datetime.now(UTC),
        )
        meal = _MockMeal(
            components=[
                _MockMealRecipe(
                    recipe=archived, recipe_id=archived.id, order_index=0
                )
            ]
        )
        session.execute.return_value = MockExecuteResult(items=[("book-1",)])

        hydrations = await service.hydrate_components(meal, user_id="user-1")
        assert len(hydrations) == 1
        assert hydrations[0].available is False
        assert hydrations[0].last_known_name == "Archived Recipe"
        assert hydrations[0].name == ""

    async def test_unshared_book_is_unavailable(self):
        service, session = _build_service()
        book = MockRecipeBook(id="book-hidden", name="Someone Else's")
        recipe = MockRecipe(
            id="recipe-1",
            name="Secret Sauce",
            recipe_book_id="book-hidden",
            recipe_book=book,
        )
        meal = _MockMeal(
            components=[
                _MockMealRecipe(
                    recipe=recipe, recipe_id=recipe.id, order_index=0
                )
            ]
        )
        # User reads nothing
        session.execute.return_value = MockExecuteResult(items=[])

        hydrations = await service.hydrate_components(meal, user_id="user-1")
        assert hydrations[0].available is False

    async def test_archived_book_is_unavailable(self):
        service, session = _build_service()
        book = MockRecipeBook(
            id="book-1",
            name="Old Book",
            archived_at=datetime.now(UTC),
        )
        recipe = MockRecipe(
            id="recipe-1",
            name="R",
            recipe_book_id="book-1",
            recipe_book=book,
        )
        meal = _MockMeal(
            components=[
                _MockMealRecipe(recipe=recipe, recipe_id=recipe.id)
            ]
        )
        session.execute.return_value = MockExecuteResult(items=[("book-1",)])

        hydrations = await service.hydrate_components(meal, user_id="user-1")
        assert hydrations[0].available is False

    async def test_missing_recipe_relationship_is_unavailable(self):
        """Guards the defensive `if recipe is None` branch in the service.

        With RESTRICT on the FK this state shouldn't be reachable in
        production, but the hydrator handles it rather than 500ing.
        """
        service, session = _build_service()
        meal = _MockMeal(
            components=[
                _MockMealRecipe(recipe=None, recipe_id="ghost", order_index=0)
            ]
        )
        session.execute.return_value = MockExecuteResult(items=[])
        hydrations = await service.hydrate_components(meal, user_id="user-1")
        assert hydrations[0].available is False
        assert hydrations[0].recipe_id == "ghost"


class TestUserHasBook:
    async def test_read_true(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(
            items=[MockRecipeBookUser(role="viewer")]
        )
        assert await service.user_has_book_read("u", "b") is True

    async def test_read_false_when_no_membership(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(items=[])
        assert await service.user_has_book_read("u", "b") is False

    async def test_write_true_for_owner(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(
            items=[MockRecipeBookUser(role="owner")]
        )
        assert await service.user_has_book_write("u", "b") is True

    async def test_write_true_for_editor(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(
            items=[MockRecipeBookUser(role="editor")]
        )
        assert await service.user_has_book_write("u", "b") is True

    async def test_write_false_for_viewer(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(
            items=[MockRecipeBookUser(role="viewer")]
        )
        assert await service.user_has_book_write("u", "b") is False

    async def test_write_false_when_no_membership(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(items=[])
        assert await service.user_has_book_write("u", "b") is False


class TestEnsureComponentsReadable:
    async def test_happy(self):
        service, session = _build_service()
        book = MockRecipeBook(id="book-1")
        r1 = MockRecipe(id="r1", recipe_book_id="book-1", recipe_book=book)
        r2 = MockRecipe(id="r2", recipe_book_id="book-1", recipe_book=book)
        # 1st execute: Recipe.in_ — returns r1,r2
        # 2nd execute: _readable_book_ids — returns [("book-1",)]
        session.execute.side_effect = [
            MockExecuteResult(items=[r1, r2]),
            MockExecuteResult(items=[("book-1",)]),
        ]
        result = await service._ensure_components_readable(
            [str(r1.id), str(r2.id)], user_id="u"
        )
        assert len(result) == 2

    async def test_missing_recipe(self):
        service, session = _build_service()
        # No recipes matched
        session.execute.side_effect = [
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[]),
        ]
        with pytest.raises(ComponentUnreadableError) as excinfo:
            await service._ensure_components_readable(
                ["r-missing"], user_id="u"
            )
        assert "r-missing" in excinfo.value.recipe_ids

    async def test_recipe_book_unreadable(self):
        service, session = _build_service()
        book = MockRecipeBook(id="book-1")
        r1 = MockRecipe(id="r1", recipe_book_id="book-1", recipe_book=book)
        # Recipe exists but user can't read its book
        session.execute.side_effect = [
            MockExecuteResult(items=[r1]),
            MockExecuteResult(items=[]),
        ]
        with pytest.raises(ComponentUnreadableError) as excinfo:
            await service._ensure_components_readable(["r1"], user_id="u")
        assert "r1" in excinfo.value.recipe_ids


class TestCreateWithComponents:
    async def test_happy(self):
        service, session = _build_service()
        book = MockRecipeBook(id="book-1")
        r1 = MockRecipe(id="r1", recipe_book_id="book-1", recipe_book=book)
        r2 = MockRecipe(id="r2", recipe_book_id="book-1", recipe_book=book)
        # Execute order:
        #   1. _ensure_components_readable → Recipe.in_
        #   2. _ensure_components_readable → _readable_book_ids
        #   3. bulk insert(MealRecipe)
        session.execute.side_effect = [
            MockExecuteResult(items=[r1, r2]),
            MockExecuteResult(items=[("book-1",)]),
            MockExecuteResult(items=[]),
        ]

        added = []
        session.add.side_effect = added.append

        meal = await service.create_with_components(
            book_id="book-1",
            name="Test",
            description="desc",
            recipe_ids=["r1", "r2"],
            user_id="u",
        )

        assert isinstance(meal, Meal)
        assert meal.name == "Test"
        assert meal.description == "desc"
        assert meal.recipe_book_id == "book-1"
        # Only the Meal goes through ORM add(); MealRecipe rows go through
        # session.execute(insert(...), [...]) to dodge the sentinel bug.
        assert len(added) == 1
        # 2 selects + 1 bulk insert = 3 execute calls.
        assert session.execute.call_count == 3
        insert_call = session.execute.call_args_list[2]
        rows = insert_call.args[1]
        assert [row["recipe_id"] for row in rows] == ["r1", "r2"]
        assert [row["order_index"] for row in rows] == [0, 1]

    async def test_rejects_unreadable(self):
        service, session = _build_service()
        session.execute.side_effect = [
            MockExecuteResult(items=[]),
            MockExecuteResult(items=[]),
        ]
        with pytest.raises(ComponentUnreadableError):
            await service.create_with_components(
                book_id="book-1",
                name="Test",
                description=None,
                recipe_ids=["r-missing1", "r-missing2"],
                user_id="u",
            )


class TestGetWithComponents:
    async def test_found(self):
        service, session = _build_service()
        meal = _MockMeal()
        session.execute.return_value = MockExecuteResult(items=[meal])
        result = await service.get_with_components("meal-1")
        assert result is meal

    async def test_not_found(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(items=[])
        assert await service.get_with_components("nope") is None


class TestArchiveRestore:
    async def test_archive_sets_timestamp(self):
        service, _ = _build_service()
        meal = _MockMeal(archived_at=None)
        result = await service.archive(meal)
        assert result.archived_at is not None

    async def test_restore_clears_timestamp(self):
        service, _ = _build_service()
        meal = _MockMeal(archived_at=datetime.now(UTC))
        result = await service.restore(meal)
        assert result.archived_at is None


class TestIsFavorited:
    async def test_returns_true_when_row_exists(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(items=["favorite-row"])
        assert await service.is_favorited(user_id="u-1", meal_id="m-1") is True

    async def test_returns_false_when_no_row(self):
        service, session = _build_service()
        session.execute.return_value = MockExecuteResult(items=[])
        assert await service.is_favorited(user_id="u-1", meal_id="m-1") is False
