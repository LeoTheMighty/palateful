"""Structural tests for mcal-1 model changes.

Verifies the MealEvent, MealRecurrenceRule, CookingLog, and
ShoppingListItem models carry the columns / indexes / check constraints
defined by the `20260418090000_add_meal_id_to_calendar_and_cooking_logs`
migration.

DB-level enforcement (inserting both recipe_id + meal_id -> IntegrityError)
is covered by `alembic check` against a live test DB in CI; here we
assert the SQLAlchemy model metadata directly, which is what the autogenerate
diff compares against.
"""

from sqlalchemy import CheckConstraint, Index

from utils.models.cooking_log import CookingLog
from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.models.shopping_list import ShoppingListItem


def _constraint_names(table_args) -> set[str]:
    names: set[str] = set()
    for ta in table_args:
        if isinstance(ta, CheckConstraint):
            if ta.name is not None:
                names.add(str(ta.name))
    return names


def _index_names(table_args) -> set[str]:
    names: set[str] = set()
    for ta in table_args:
        if isinstance(ta, Index):
            names.add(str(ta.name))
    return names


class TestMealEventModel:
    def test_meal_id_column_present_and_nullable(self):
        col = MealEvent.__table__.c.meal_id
        assert col.nullable is True
        # FK targets meals.id with SET NULL
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "meals.id"
        assert fks[0].ondelete == "SET NULL"

    def test_recipe_id_still_nullable(self):
        # Regression: recipe_id must remain nullable for legacy free-text events.
        assert MealEvent.__table__.c.recipe_id.nullable is True

    def test_xor_check_constraint_declared(self):
        names = _constraint_names(MealEvent.__table_args__)
        assert "ck_meal_events_recipe_xor_meal" in names

    def test_meal_id_index_declared(self):
        names = _index_names(MealEvent.__table_args__)
        assert "ix_meal_events_meal_id" in names

    def test_relationship_meal_exists(self):
        # Avoids N+1 in list/get handlers — mcal-3 relies on the relationship.
        assert hasattr(MealEvent, "meal")


class TestMealRecurrenceRuleModel:
    def test_meal_id_column_present_and_nullable(self):
        col = MealRecurrenceRule.__table__.c.meal_id
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "meals.id"
        assert fks[0].ondelete == "SET NULL"

    def test_recipe_id_still_nullable(self):
        assert MealRecurrenceRule.__table__.c.recipe_id.nullable is True

    def test_xor_check_constraint_declared(self):
        names = _constraint_names(MealRecurrenceRule.__table_args__)
        assert "ck_meal_recurrence_rules_recipe_xor_meal" in names

    def test_meal_id_index_declared(self):
        names = _index_names(MealRecurrenceRule.__table_args__)
        assert "ix_meal_recurrence_rules_meal_id" in names

    def test_relationship_meal_exists(self):
        assert hasattr(MealRecurrenceRule, "meal")


class TestCookingLogModel:
    def test_recipe_id_becomes_nullable(self):
        # Parent Meal-level logs have recipe_id NULL; must be permitted.
        assert CookingLog.__table__.c.recipe_id.nullable is True

    def test_meal_id_column_present_and_nullable(self):
        col = CookingLog.__table__.c.meal_id
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "meals.id"
        assert fks[0].ondelete == "SET NULL"

    def test_parent_meal_log_id_self_fk(self):
        col = CookingLog.__table__.c.parent_meal_log_id
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "cooking_logs.id"
        assert fks[0].ondelete == "CASCADE"

    def test_target_check_constraint_declared(self):
        names = _constraint_names(CookingLog.__table_args__)
        assert "ck_cooking_logs_target" in names

    def test_relationships_exist(self):
        # Handlers in mcal-6 rely on these to hydrate parent/child rows.
        assert hasattr(CookingLog, "meal")
        assert hasattr(CookingLog, "parent_meal_log")


class TestShoppingListItemModel:
    def test_source_meal_id_column_present(self):
        col = ShoppingListItem.__table__.c.source_meal_id
        assert col.nullable is True
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].target_fullname == "meals.id"
        assert fks[0].ondelete == "SET NULL"

    def test_source_meal_relationship_exists(self):
        assert hasattr(ShoppingListItem, "source_meal")

    def test_no_new_check_constraint(self):
        # Invariant: source_meal_id is purely descriptive provenance. A
        # PopulateFromCalendar row from a Meal event can legitimately set
        # recipe_id + meal_event_id + source_meal_id simultaneously.
        table_args = getattr(ShoppingListItem, "__table_args__", ())
        existing_cks = [
            ta for ta in table_args if isinstance(ta, CheckConstraint)
        ]
        source_meal_cks = [
            c for c in existing_cks if c.name and "source_meal" in c.name
        ]
        assert source_meal_cks == []
