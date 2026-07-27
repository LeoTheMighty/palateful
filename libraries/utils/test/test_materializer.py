"""Unit tests for the recurrence materializer's expected-date logic."""

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace


def _make_rule(**overrides):
    base = {
        "id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "title": "Pizza",
        "recipe_id": None,
        "meal_id": None,
        "meal_type": "dinner",
        "weekdays": ["fri"],
        "interval": "weekly",
        "monthly_nth": None,
        "start_date": date(2026, 1, 5),  # Monday
        "end_date": None,
        "tz_name": "America/Los_Angeles",
        "is_shared": False,
        "calendar_id": uuid.uuid4(),
        "materialized_through": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ----------------------------------------------------------------------
# In-memory stand-in for a sync Session, enough for materialize().
#
# There is no DB-backed test harness under libraries/utils, so the fake
# interprets the handful of SQLAlchemy constructs materialize() actually
# emits: `query(Model).filter(<binary expr>...).all()/.first()`, `delete()`,
# and a postgres `INSERT ... ON CONFLICT DO NOTHING`.


def _matches(criterion, row) -> bool:
    """Evaluate a simple `Column <op> value` / `Column IS NULL` criterion."""
    import operator as _op

    column = criterion.left.name
    actual = getattr(row, column, None)
    expected = getattr(criterion.right, "value", None)
    # `Column.is_(None)` / `isnot(None)` carry SQLAlchemy's own operator
    # callables, which expect ClauseElements — map them to identity checks.
    if criterion.operator.__name__ == "is_":
        return actual is expected
    if criterion.operator.__name__ in ("is_not", "isnot"):
        return actual is not expected
    return bool(getattr(_op, criterion.operator.__name__, criterion.operator)(
        actual, expected
    ))


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *criteria):
        rows = self._rows
        for criterion in criteria:
            rows = [r for r in rows if _matches(criterion, r)]
        return _FakeQuery(rows)

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Holds MealEvent rows in a list and enforces the partial unique index."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def query(self, model):
        if model.__name__ == "MealEvent":
            return _FakeQuery(self.rows)
        # Meal / Recipe lookups in _resolve_title — nothing seeded.
        return _FakeQuery([])

    def delete(self, obj):
        self.rows = [r for r in self.rows if r is not obj]

    def execute(self, stmt):
        from utils.models.meal_event import MealEvent

        # pg_insert(...).values([...]) stashes the rows in _multi_values.
        for values in stmt._multi_values[0]:
            # uq_meal_events_rule_scheduled_at WHERE recurrence_rule_id IS NOT NULL
            conflict = any(
                r.recurrence_rule_id is not None
                and r.recurrence_rule_id == values["recurrence_rule_id"]
                and r.scheduled_at == values["scheduled_at"]
                for r in self.rows
            )
            if conflict:
                continue  # ON CONFLICT DO NOTHING
            self.rows.append(MealEvent(id=uuid.uuid4(), **values))

    def live_rows(self):
        return [r for r in self.rows if r.archived_at is None]


def _daily_rule(**overrides):
    """A rule that fires every day starting today, in UTC."""
    base = {
        "interval": "weekly",
        "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "start_date": date.today(),
        "tz_name": "UTC",
    }
    base.update(overrides)
    return _make_rule(**base)


class TestExpectedDatesWeekly:
    def test_weekly_one_weekday(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="weekly",
            weekdays=["fri"],
            start_date=date(2026, 1, 2),  # Friday
        )
        result = _expected_dates(rule, date(2026, 1, 2), date(2026, 1, 23))
        assert result == [date(2026, 1, 2), date(2026, 1, 9), date(2026, 1, 16)]

    def test_weekly_multi_weekday(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="weekly",
            weekdays=["mon", "wed"],
            start_date=date(2026, 1, 5),  # Monday
        )
        result = _expected_dates(rule, date(2026, 1, 5), date(2026, 1, 19))
        assert result == [
            date(2026, 1, 5),
            date(2026, 1, 7),
            date(2026, 1, 12),
            date(2026, 1, 14),
        ]


class TestExpectedDatesBiweekly:
    def test_biweekly_anchor_parity(self):
        """Biweekly means every-other-week measured from start_date's Monday."""
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="biweekly",
            weekdays=["fri"],
            start_date=date(2026, 1, 2),  # Friday
        )
        result = _expected_dates(rule, date(2026, 1, 2), date(2026, 2, 13))
        # Expected Fridays: Jan 2, Jan 16, Jan 30, Feb 13 (skipping alternating weeks)
        assert result == [
            date(2026, 1, 2),
            date(2026, 1, 16),
            date(2026, 1, 30),
        ]

    def test_biweekly_end_date_bound(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="biweekly",
            weekdays=["fri"],
            start_date=date(2026, 1, 2),
        )
        result = _expected_dates(rule, date(2026, 1, 10), date(2026, 1, 20))
        assert result == [date(2026, 1, 16)]


class TestExpectedDatesMonthly:
    def test_monthly_first_saturday_across_months(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="first",
            weekdays=["sat"],
            start_date=date(2026, 1, 1),
        )
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 4, 1))
        # First Saturdays: Jan 3, Feb 7, Mar 7
        assert result == [date(2026, 1, 3), date(2026, 2, 7), date(2026, 3, 7)]

    def test_monthly_last_friday_in_4_friday_month(self):
        """February 2026 has exactly 4 Fridays (6, 13, 20, 27).
        "last" == "fourth" semantics — matches the 4th.
        """
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="last",
            weekdays=["fri"],
            start_date=date(2026, 2, 1),
        )
        result = _expected_dates(rule, date(2026, 2, 1), date(2026, 3, 1))
        assert result == [date(2026, 2, 27)]

    def test_monthly_last_friday_in_5_friday_month(self):
        """January 2026 has 5 Fridays (2, 9, 16, 23, 30). "last" matches the 5th."""
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="last",
            weekdays=["fri"],
            start_date=date(2026, 1, 1),
        )
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 2, 1))
        assert result == [date(2026, 1, 30)]

    def test_monthly_end_date_cutoff(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="first",
            weekdays=["sat"],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )
        # End-date bound is enforced at the materialize() level, not
        # _expected_dates. This test asserts that the raw expansion over
        # [start, end+1) returns the expected monthly rows.
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 3, 1))
        assert result == [date(2026, 1, 3), date(2026, 2, 7)]

    def test_monthly_fourth_exists(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="fourth",
            weekdays=["fri"],
            start_date=date(2026, 1, 1),
        )
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 2, 1))
        assert result == [date(2026, 1, 23)]

    def test_monthly_fifth_missing_returns_empty(self):
        """Feb 2026 has only 4 Fridays; monthly_nth="fourth" finds day 27,
        and since the only valid 'nth' options exclude 'fifth', there's no
        case where a >4-Friday month gives nothing. But requesting
        monthly_nth='fourth' in a 4-Friday month still returns the 4th."""
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="fourth",
            weekdays=["fri"],
            start_date=date(2026, 2, 1),
        )
        result = _expected_dates(rule, date(2026, 2, 1), date(2026, 3, 1))
        assert result == [date(2026, 2, 27)]

    def test_monthly_december_rollover(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="first",
            weekdays=["sun"],
            start_date=date(2025, 12, 1),
        )
        result = _expected_dates(rule, date(2025, 12, 1), date(2026, 2, 1))
        # Dec 7 2025 (Sun), Jan 4 2026 (Sun)
        assert result == [date(2025, 12, 7), date(2026, 1, 4)]

    def test_monthly_no_weekdays_returns_empty(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth="first",
            weekdays=[],
        )
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 4, 1))
        assert result == []

    def test_monthly_nth_missing_returns_empty(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(
            interval="monthly",
            monthly_nth=None,
            weekdays=["sat"],
        )
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 4, 1))
        assert result == []


class TestExpectedDatesEmpty:
    def test_from_date_after_to_date_returns_empty(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule()
        result = _expected_dates(rule, date(2026, 2, 1), date(2026, 1, 1))
        assert result == []

    def test_unknown_weekdays_returns_empty(self):
        from utils.recurrence.materializer import _expected_dates

        rule = _make_rule(weekdays=["xyz"])
        result = _expected_dates(rule, date(2026, 1, 1), date(2026, 3, 1))
        assert result == []


class TestResolveTitleMealBranch:
    """mcal-6: `_resolve_title` prefers `rule.meal_id` when both FKs set,
    and falls back through recipe then rule.title."""

    def _fake_db(self, *, meal_match=None, recipe_match=None):
        """A minimal mock that honors Session.query(Meal).filter(...).first()."""

        class _Result:
            def __init__(self, value):
                self._value = value

            def filter(self, *a, **kw):
                return self

            def first(self):
                return self._value

        class _DB:
            def __init__(self, meal, recipe):
                self._meal = meal
                self._recipe = recipe

            def query(self, model):
                # Model import lives inside materializer — check by class name.
                if model.__name__ == "Meal":
                    return _Result(self._meal)
                if model.__name__ == "Recipe":
                    return _Result(self._recipe)
                return _Result(None)

        return _DB(meal_match, recipe_match)

    def test_meal_linked_rule_resolves_title_to_meal_name(self):
        from types import SimpleNamespace
        from utils.recurrence.materializer import _resolve_title

        meal = SimpleNamespace(id=uuid.uuid4(), name="Kale Salad Meal")
        rule = _make_rule(recipe_id=None, meal_id=meal.id)
        db = self._fake_db(meal_match=meal)
        assert _resolve_title(rule, db) == "Kale Salad Meal"

    def test_meal_id_wins_over_recipe_id_when_both_unexpectedly_set(self):
        """XOR is schema-enforced so both-set shouldn't happen in prod;
        defense-in-depth: the materializer picks Meal over Recipe."""
        from types import SimpleNamespace
        from utils.recurrence.materializer import _resolve_title

        meal = SimpleNamespace(id=uuid.uuid4(), name="The Meal")
        recipe = SimpleNamespace(id=uuid.uuid4(), name="The Recipe")
        rule = _make_rule(recipe_id=recipe.id, meal_id=meal.id)
        db = self._fake_db(meal_match=meal, recipe_match=recipe)
        assert _resolve_title(rule, db) == "The Meal"

    def test_meal_id_set_but_meal_missing_falls_through(self):
        from utils.recurrence.materializer import _resolve_title

        rule = _make_rule(
            recipe_id=None, meal_id=uuid.uuid4(), title="fallback",
        )
        db = self._fake_db(meal_match=None)
        # Falls to recipe (None) → falls to title.
        assert _resolve_title(rule, db) == "fallback"

    def test_meal_and_recipe_both_missing_falls_to_default(self):
        from utils.recurrence.materializer import _resolve_title

        rule = _make_rule(recipe_id=None, meal_id=None, title=None)
        db = self._fake_db()
        assert _resolve_title(rule, db) == "Meal"


class TestMaterializedRowFlags:
    """rcres1 AC4: materialized rows carry `is_recurring=True`.

    Clients key off `recurrence_rule_id`, but `is_recurring` ships on every
    meal-event response schema, so leaving it at its False default made the
    flag actively wrong on rule-generated rows.
    """

    def test_materialized_rows_set_is_recurring(self):
        from utils.recurrence.materializer import materialize

        rule = _daily_rule()
        db = _FakeSession()
        rows = materialize(rule, date.today() + timedelta(days=7), db)

        assert rows
        assert all(r.is_recurring is True for r in rows)
        assert all(r.recurrence_rule_id == rule.id for r in rows)


class TestMaterializeTombstones:
    """rcres1: a single-occurrence deletion must survive window advances.

    `DeleteRecurrenceRule._delete_single_occurrence` tombstones the row —
    sets `archived_at`, keeps `recurrence_rule_id`. The old code detached the
    row instead, which hid it from materialize()'s dedup query and re-inserted
    the slot on the next pass.
    """

    def _seed(self, rule, days=7):
        db = _FakeSession()
        from utils.recurrence.materializer import materialize

        materialize(rule, date.today() + timedelta(days=days), db)
        return db

    def _tombstone(self, db, index=2):
        """Emulate the endpoint's single-occurrence delete on the Nth row."""
        victim = sorted(db.rows, key=lambda r: r.scheduled_at)[index]
        victim.archived_at = datetime.now(UTC)
        return victim

    def test_deleted_occurrence_not_reinserted_on_window_advance(self):
        from utils.recurrence.materializer import materialize

        rule = _daily_rule()
        db = self._seed(rule)
        assert len(db.rows) == 7

        victim_ts = self._tombstone(db).scheduled_at

        materialize(rule, date.today() + timedelta(days=14), db)

        at_slot = [r for r in db.rows if r.scheduled_at == victim_ts]
        assert len(at_slot) == 1, "the deleted occurrence was resurrected"
        assert at_slot[0].archived_at is not None
        # The advance still filled in the newly-in-window days.
        assert len(db.live_rows()) == 13

    def test_tombstone_survives_repeated_passes(self):
        from utils.recurrence.materializer import materialize

        rule = _daily_rule()
        db = self._seed(rule)
        victim_ts = self._tombstone(db).scheduled_at

        for extra in (14, 21, 28):
            materialize(rule, date.today() + timedelta(days=extra), db)

        at_slot = [r for r in db.rows if r.scheduled_at == victim_ts]
        assert len(at_slot) == 1
        assert at_slot[0].archived_at is not None

    def test_tombstone_excluded_from_returned_rows(self):
        from utils.recurrence.materializer import materialize

        rule = _daily_rule()
        db = self._seed(rule)
        victim_ts = self._tombstone(db).scheduled_at

        returned = materialize(rule, date.today() + timedelta(days=7), db)

        assert all(r.scheduled_at != victim_ts for r in returned)
        assert all(r.archived_at is None for r in returned)
        assert len(returned) == 6

    def test_tombstone_title_not_rewritten_on_rename(self):
        from utils.recurrence.materializer import materialize

        rule = _daily_rule(title="Pizza")
        db = self._seed(rule)
        victim = self._tombstone(db)

        rule.title = "Calzone"
        materialize(rule, date.today() + timedelta(days=7), db)

        assert victim.title == "Pizza"
        assert all(r.title == "Calzone" for r in db.live_rows())

    def test_tombstone_dropped_when_slot_leaves_expected_set(self):
        """Editing the rule so the slot no longer recurs removes the tombstone
        along with the live rows — there's nothing left to suppress."""
        from utils.recurrence.materializer import materialize

        rule = _daily_rule()
        db = self._seed(rule)
        victim_ts = self._tombstone(db).scheduled_at
        victim_weekday = victim_ts.date().weekday()

        # Narrow the rule to a single weekday that isn't the tombstoned one.
        from utils.recurrence.materializer import WEEKDAY_NAMES

        keep = WEEKDAY_NAMES[(victim_weekday + 1) % 7]
        rule.weekdays = [keep]
        materialize(rule, date.today() + timedelta(days=7), db)

        assert all(r.scheduled_at != victim_ts for r in db.rows)

    def test_detached_row_still_resurrects_documenting_the_bug(self):
        """Guard on the root cause: a row detached from its rule is invisible
        to the dedup query, so the slot re-inserts. This is what the old
        `_delete_single_occurrence` did — the assertion pins *why* the
        endpoint must not set `recurrence_rule_id = None`."""
        from utils.recurrence.materializer import materialize

        rule = _daily_rule()
        db = self._seed(rule)

        victim = self._tombstone(db)
        victim_ts = victim.scheduled_at
        victim.recurrence_rule_id = None  # the old, buggy detach

        materialize(rule, date.today() + timedelta(days=14), db)

        at_slot = [r for r in db.rows if r.scheduled_at == victim_ts]
        assert len(at_slot) == 2, "detaching re-inserts the slot (root cause)"
        assert sum(1 for r in at_slot if r.archived_at is None) == 1
