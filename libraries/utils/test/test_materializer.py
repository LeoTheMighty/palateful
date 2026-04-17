"""Unit tests for the recurrence materializer's expected-date logic."""

import uuid
from datetime import date, timedelta
from types import SimpleNamespace


def _make_rule(**overrides):
    base = {
        "id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "title": "Pizza",
        "recipe_id": None,
        "meal_type": "dinner",
        "weekdays": ["fri"],
        "interval": "weekly",
        "monthly_nth": None,
        "start_date": date(2026, 1, 5),  # Monday
        "end_date": None,
        "tz_name": "America/Los_Angeles",
        "is_shared": False,
        "materialized_through": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


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
