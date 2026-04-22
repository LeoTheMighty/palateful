"""Unit tests for `import_notifications.notify_import_needs_review`.

Covers the rich-copy refactor: single-recipe imports surface the recipe
name + cover image; bulk imports use the count and skip the per-item
lookup; missing data falls back gracefully.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from utils.services.import_notifications import notify_import_needs_review
from utils.services.push_notification import NotificationType


def _make_database(*, user, item):
    """Database mock matching the shape `notify_import_needs_review` uses."""
    db = MagicMock()
    db.find_by.return_value = user
    # query(ImportItem).filter_by(...).order_by(...).first() → item
    query_chain = MagicMock()
    query_chain.filter_by.return_value.order_by.return_value.first.return_value = item
    db.db.query.return_value = query_chain
    return db


def _make_user(prefs: dict | None = None):
    user = MagicMock()
    user.id = "user-1"
    user.push_tokens = ["tok-1"]
    user.notification_preferences = prefs or {}
    return user


def _make_job(*, pending_review_items: int = 1):
    job = MagicMock()
    job.id = "job-1"
    job.user_id = "user-1"
    job.pending_review_items = pending_review_items
    return job


def _make_item(parsed_recipe: dict | None):
    item = MagicMock()
    item.parsed_recipe = parsed_recipe
    return item


def _capture_send(mock_push_service):
    """Returns the PushNotification arg passed to `send_to_user`."""
    assert mock_push_service.send_to_user.call_count == 1
    args, _ = mock_push_service.send_to_user.call_args
    # signature: (user, notification, db_session)
    return args[1]


# Test A: single-recipe job with parsed_recipe.name set → push title contains the name.
def test_single_with_recipe_name_in_title():
    user = _make_user()
    item = _make_item({"name": "Sweet Potato Quiche", "image_url": None})
    job = _make_job(pending_review_items=1)
    db = _make_database(user=user, item=item)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    notification = _capture_send(mock_push_service)
    assert "Sweet Potato Quiche" in notification.title
    assert notification.notification_type == NotificationType.IMPORT_NEEDS_REVIEW
    assert notification.image_url is None


# Test B: single-recipe job with no name in parsed_recipe → fallback copy.
def test_single_with_no_name_falls_back():
    user = _make_user()
    item = _make_item({"image_url": "https://x/img.jpg"})  # no `name`
    job = _make_job(pending_review_items=1)
    db = _make_database(user=user, item=item)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    notification = _capture_send(mock_push_service)
    assert notification.title == "Your recipe is ready to review"


# Test C: bulk job (5 items) → bulk variant + count in body. No item lookup performed.
def test_bulk_variant_skips_item_lookup():
    user = _make_user()
    job = _make_job(pending_review_items=5)
    db = _make_database(user=user, item=None)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    notification = _capture_send(mock_push_service)
    assert notification.title == "Your bulk import is ready"
    assert "5 recipes" in notification.body
    # bulk path must NOT touch `db.db.query` (round-trip saved).
    db.db.query.assert_not_called()


# Test D: single-recipe with image_url present → notification.image_url set.
def test_single_image_url_passed_through():
    user = _make_user()
    item = _make_item({
        "name": "Cookies",
        "image_url": "https://example.com/cookies.jpg",
    })
    job = _make_job(pending_review_items=1)
    db = _make_database(user=user, item=item)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    notification = _capture_send(mock_push_service)
    assert notification.image_url == "https://example.com/cookies.jpg"


# Test E: single-recipe with image_url absent → image_url is None.
def test_single_image_url_absent_is_none():
    user = _make_user()
    item = _make_item({"name": "Beans"})  # no image_url
    job = _make_job(pending_review_items=1)
    db = _make_database(user=user, item=item)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    notification = _capture_send(mock_push_service)
    assert notification.image_url is None


# Bonus: parsed_recipe missing entirely → graceful fallback.
def test_missing_parsed_recipe_falls_back():
    user = _make_user()
    item = _make_item(None)
    job = _make_job(pending_review_items=1)
    db = _make_database(user=user, item=item)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    notification = _capture_send(mock_push_service)
    assert notification.title == "Your recipe is ready to review"
    assert notification.image_url is None


# Bonus: review_count == 0 → no send.
def test_review_count_zero_does_not_send():
    user = _make_user()
    job = _make_job(pending_review_items=0)
    db = _make_database(user=user, item=None)

    mock_push_service = MagicMock()
    mock_push_service.is_available = True
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    mock_push_service.send_to_user.assert_not_called()


# Bonus: push service unavailable → no send.
def test_push_service_unavailable_no_send():
    user = _make_user()
    job = _make_job(pending_review_items=1)
    db = _make_database(user=user, item=None)

    mock_push_service = MagicMock()
    mock_push_service.is_available = False
    with patch(
        "utils.services.import_notifications.get_push_service",
        return_value=mock_push_service,
    ):
        notify_import_needs_review(db, job)

    mock_push_service.send_to_user.assert_not_called()
