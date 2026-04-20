"""Unit tests for the pantry decrement subscriber (pantry-4)."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from conftest import (
    MockIngredient,
    MockPantry,
    MockPantryIngredient,
    MockPantryUser,
    MockQuery,
    MockRecipe,
    MockRecipeIngredient,
    MockUser,
)
from utils.events import MealEventCompleted


def _event(user_id, meal_event_id, recipe_id, servings=None):
    return MealEventCompleted(
        user_id=user_id,
        meal_event_id=meal_event_id,
        recipe_id=recipe_id,
        servings=servings,
    )


def _make_mock_database(recipe, membership, pantry, pantry_rows_by_ingredient):
    """Build a MagicMock Database for the subscriber.

    ``pantry_rows_by_ingredient`` maps ``ingredient_id`` → MockPantryIngredient.
    """
    from utils.models.pantry import Pantry
    from utils.models.pantry_ingredient import PantryIngredient
    from utils.models.pantry_user import PantryUser
    from utils.models.recipe import Recipe

    db = MagicMock()
    added_rows: list = []
    db.db.add.side_effect = lambda row: added_rows.append(row)
    db.db.commit = MagicMock()
    db.db.rollback = MagicMock()
    db.close = MagicMock()
    db.lock = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))
    db.added_rows = added_rows

    def query_side_effect(model_class, *args, **kwargs):
        if model_class is Recipe:
            return MockQuery([recipe])
        if model_class is PantryUser:
            return MockQuery([membership] if membership else [])
        if model_class is PantryIngredient:
            # The decrement helper queries once per recipe ingredient.
            call_args = query_side_effect.calls
            call_args.append(True)
            ingredient_id = query_side_effect.pending_ingredient_ids.pop(0) if query_side_effect.pending_ingredient_ids else None
            row = pantry_rows_by_ingredient.get(ingredient_id) if ingredient_id else None
            return MockQuery([row] if row else [])
        return MockQuery([])

    query_side_effect.calls = []
    query_side_effect.pending_ingredient_ids = [
        str(ri.ingredient_id) for ri in recipe.ingredients
    ]
    db.db.query.side_effect = query_side_effect

    def find_by(model_class, **kwargs):
        if model_class is Pantry:
            return pantry
        if model_class is PantryUser:
            return membership
        return None
    db.find_by.side_effect = find_by
    return db


def _invoke(event, db):
    from api.subscribers.pantry_meal_subscriber import handle_meal_event_completed

    with patch(
        "api.subscribers.pantry_meal_subscriber.Database", return_value=db
    ):
        handle_meal_event_completed(event)


class TestDecrementSubscriber:
    def test_happy_path_decrements(self):
        user = MockUser()
        ing = MockIngredient(canonical_name="flour")
        ri = MockRecipeIngredient(
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("50.000"),
            unit_normalized="g",
        )
        recipe = MockRecipe(id=str(uuid.uuid4()), servings=1, ingredients=[ri])
        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(user.id), pantry_id=str(pantry.id))
        pantry_row = MockPantryIngredient(
            pantry_id=str(pantry.id),
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("100.000"),
            unit_normalized="g",
        )

        db = _make_mock_database(
            recipe, membership, pantry, {str(ing.id): pantry_row}
        )

        _invoke(
            _event(str(user.id), uuid.uuid4(), uuid.UUID(recipe.id)), db
        )

        assert pantry_row.quantity_normalized == Decimal("50.000")
        assert pantry_row.archived_at is None
        # One audit event row added
        assert len(db.added_rows) == 1
        event_row = db.added_rows[0]
        assert event_row.event_type == "decrement"
        assert event_row.delta_quantity == Decimal("-50.000")

    def test_unit_mismatch_is_silent_skip(self):
        user = MockUser()
        ing = MockIngredient(canonical_name="onion")
        ri = MockRecipeIngredient(
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("1.000"),
            unit_normalized="cup",
        )
        recipe = MockRecipe(servings=1, ingredients=[ri])
        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(user.id), pantry_id=str(pantry.id))
        pantry_row = MockPantryIngredient(
            pantry_id=str(pantry.id),
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("2.000"),
            unit_normalized="each",
        )

        db = _make_mock_database(
            recipe, membership, pantry, {str(ing.id): pantry_row}
        )
        _invoke(_event(str(user.id), uuid.uuid4(), uuid.UUID(recipe.id)), db)

        # Unchanged
        assert pantry_row.quantity_normalized == Decimal("2.000")
        assert pantry_row.unit_normalized == "each"
        # No audit row for skipped decrement
        assert db.added_rows == []

    def test_missing_pantry_row_is_silent_skip(self):
        user = MockUser()
        ing = MockIngredient()
        ri = MockRecipeIngredient(
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("100.000"),
            unit_normalized="g",
        )
        recipe = MockRecipe(servings=1, ingredients=[ri])
        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(user.id), pantry_id=str(pantry.id))

        db = _make_mock_database(recipe, membership, pantry, {})
        _invoke(_event(str(user.id), uuid.uuid4(), uuid.UUID(recipe.id)), db)

        assert db.added_rows == []

    def test_clamp_to_zero_archives_row(self):
        user = MockUser()
        ing = MockIngredient()
        ri = MockRecipeIngredient(
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("100.000"),
            unit_normalized="g",
        )
        recipe = MockRecipe(servings=1, ingredients=[ri])
        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(user.id), pantry_id=str(pantry.id))
        pantry_row = MockPantryIngredient(
            pantry_id=str(pantry.id),
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("10.000"),
            unit_normalized="g",
        )

        db = _make_mock_database(
            recipe, membership, pantry, {str(ing.id): pantry_row}
        )
        _invoke(_event(str(user.id), uuid.uuid4(), uuid.UUID(recipe.id)), db)

        assert pantry_row.quantity_normalized == Decimal("0")
        assert pantry_row.archived_at is not None
        # audit records the ACTUAL amount consumed, not the attempted 100g
        assert db.added_rows[0].delta_quantity == Decimal("-10.000")

    def test_no_recipe_servings_skips_all(self):
        user = MockUser()
        ing = MockIngredient()
        ri = MockRecipeIngredient(
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("100.000"),
            unit_normalized="g",
        )
        recipe = MockRecipe(servings=0, ingredients=[ri])
        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(user.id), pantry_id=str(pantry.id))

        db = _make_mock_database(recipe, membership, pantry, {})
        _invoke(_event(str(user.id), uuid.uuid4(), uuid.UUID(recipe.id)), db)

        assert db.added_rows == []

    def test_subscriber_swallows_exceptions(self):
        user = MockUser()
        recipe_id = uuid.uuid4()

        db = MagicMock()
        # Throw on the very first query to simulate a DB error mid-flight.
        db.db.query.side_effect = RuntimeError("kaboom")
        db.close = MagicMock()
        db.db.rollback = MagicMock()

        with patch(
            "api.subscribers.pantry_meal_subscriber.Database", return_value=db
        ):
            from api.subscribers.pantry_meal_subscriber import (
                handle_meal_event_completed,
            )
            # Must not raise — the caller's request already committed.
            handle_meal_event_completed(
                _event(uuid.uuid4(), uuid.uuid4(), recipe_id)
            )

        assert db.close.called
        # Rollback was called to leave a clean transaction.
        assert db.db.rollback.called

    def test_scales_by_servings_when_event_servings_provided(self):
        """If event.servings is set, the scale = event/recipe servings."""
        user = MockUser()
        ing = MockIngredient(canonical_name="flour")
        ri = MockRecipeIngredient(
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("100.000"),
            unit_normalized="g",
        )
        # Recipe natively makes 4 servings, event only cooked 2 → half.
        recipe = MockRecipe(id=str(uuid.uuid4()), servings=4, ingredients=[ri])
        pantry = MockPantry()
        membership = MockPantryUser(user_id=str(user.id), pantry_id=str(pantry.id))
        pantry_row = MockPantryIngredient(
            pantry_id=str(pantry.id),
            ingredient_id=str(ing.id),
            quantity_normalized=Decimal("200.000"),
            unit_normalized="g",
        )

        db = _make_mock_database(
            recipe, membership, pantry, {str(ing.id): pantry_row}
        )
        _invoke(
            _event(str(user.id), uuid.uuid4(), uuid.UUID(recipe.id), servings=2.0),
            db,
        )

        # 100g × (2/4) = 50g consumed. Pantry was 200g → 150g remains.
        assert pantry_row.quantity_normalized == Decimal("150.000")

    def test_missing_recipe_returns_early(self):
        """If the recipe can't be loaded, log a warning and skip."""
        from utils.models.recipe import Recipe

        db = MagicMock()
        db.db.query.side_effect = lambda model, *a, **kw: MockQuery([])
        db.close = MagicMock()

        with patch(
            "api.subscribers.pantry_meal_subscriber.Database", return_value=db
        ):
            from api.subscribers.pantry_meal_subscriber import (
                handle_meal_event_completed,
            )
            handle_meal_event_completed(
                _event(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
            )

        # Bailed out before touching pantry or rollback.
        assert db.close.called
        assert not db.db.rollback.called
