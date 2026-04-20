"""afh-6 deploy-order CI guard.

The Notifications tab's list + count endpoints (afh-1a/afh-2) import
``NOTIFICATION_TAB_TYPES`` from ``utils.models.user_activity`` to
scope queries to partner-action-style rows only. That constant was
introduced in epic-activity-badge-integrity (abi-1). If a rebase ever
lands an Activity Hub code change BEFORE the allow-list constant is
merged on main, the affected endpoints (``list_activities`` +
``see_all_count``) would fail at import-time in production — a cold-
deploy fault that a passing test suite would miss.

This test is a cheap static assertion that runs on every CI push. It
fails at import-time if the constant is missing or not a populated
``frozenset`` — which means the deploy-order guard trips before
anything downstream has a chance to 500 in prod.
"""

from utils.models.user_activity import NOTIFICATION_TAB_TYPES


def test_notification_tab_types_is_a_non_empty_frozenset():
    """The list + count endpoints require the allow-list to exist as
    an iterable with at least ``partner_action`` in it (abi-1's
    minimum contract). A test failing here at import-time means the
    abi-1 merge hasn't landed — or somebody deleted the constant
    without migrating the callers."""
    assert isinstance(NOTIFICATION_TAB_TYPES, frozenset), (
        "NOTIFICATION_TAB_TYPES must be a frozenset; list_activities "
        "and see_all_count pass it to SQLAlchemy .in_() which expects "
        "an immutable iterable"
    )
    assert len(NOTIFICATION_TAB_TYPES) > 0, (
        "NOTIFICATION_TAB_TYPES is empty — the Notifications tab would "
        "render zero rows on every user. Add at least 'partner_action'."
    )
    assert "partner_action" in NOTIFICATION_TAB_TYPES, (
        "'partner_action' is the foundational Notifications-tab type "
        "(ahr-3). Removing it silently empties the tab."
    )
