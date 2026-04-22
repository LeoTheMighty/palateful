"""Meal-event push fan-out helpers (meal-3, meal-4).

This module is the *shared* home for meal-event notification dispatch —
both the API-side update endpoint (meal-4) and the Celery beat task
(meal-3) import from here. The older shims in
`services/api/src/api/v1/meal_event/utils/notifications.py` remain for
the `MEAL_EVENT_INVITE` path (which doesn't live in libraries).

Layering:
  - `notification_copy.meal_event_reminder / meal_event_updated`
    produces title/body tuples.
  - This module assembles `PushNotification` dataclasses + fan-out to
    recipients via `PushNotificationService.send_to_user`, which
    applies per-recipient category prefs + quiet hours.
  - The Celery task is a thin wrapper: query the DB window, call
    `notify_meal_event_reminder` per event, commit `last_reminder_sent_at`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from utils.services.notification_copy import (
    _resolve_actor_name,
    meal_event_reminder as _meal_event_reminder_copy,
    meal_event_updated as _meal_event_updated_copy,
)
from utils.services.push_notification import (
    NotificationType,
    PushNotification,
    get_push_service,
)

logger = logging.getLogger(__name__)


def _minutes_until(
    now: datetime,
    scheduled_at: datetime,
) -> int:
    """Whole-minute delta from `now` to `scheduled_at`.

    Negative deltas are clamped to 0 — a reminder that fires after
    `scheduled_at` should still read "now", not "-5 minutes ago".
    """
    delta = scheduled_at - now
    minutes = int(delta.total_seconds() // 60)
    return max(0, minutes)


def _resolve_recipients(meal_event: Any) -> list[Any]:
    """Accepted participants plus owner fallback.

    Owner is the first invariant — every meal has exactly one. When the
    owner auto-added themselves as a `host` participant (the default
    for `create_meal_event`), they're in the participants list; we
    dedupe in that case. Declined / invited / maybe participants are
    skipped — only accepted-RSVPs get the reminder.
    """
    recipients: list[Any] = []
    seen: set[str] = set()

    for p in getattr(meal_event, "participants", None) or []:
        if getattr(p, "status", None) != "accepted":
            continue
        user = getattr(p, "user", None)
        if user is None:
            continue
        user_id = str(getattr(user, "id", ""))
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        recipients.append(user)

    # Owner-as-last-resort: typically the owner is in participants
    # (with role=host, status=accepted). If they aren't — e.g. a row
    # from an older flow that never wrote the participant — fall back
    # to the direct `owner` relationship so they still get the ping.
    owner = getattr(meal_event, "owner", None)
    if owner is not None:
        owner_id = str(getattr(owner, "id", ""))
        if owner_id and owner_id not in seen:
            seen.add(owner_id)
            recipients.append(owner)

    return recipients


def _partner_first_name(
    recipient: Any,
    all_recipients: Iterable[Any],
) -> str | None:
    """For the shared-meal body ("Sarah is also cooking"), pick the
    first OTHER accepted participant's first name. `None` when this is
    a solo meal (single recipient)."""
    recipient_id = str(getattr(recipient, "id", ""))
    for other in all_recipients:
        other_id = str(getattr(other, "id", ""))
        if other_id and other_id != recipient_id:
            return _resolve_actor_name(other)
    return None


def notify_meal_event_reminder(
    meal_event: Any,
    *,
    db_session: Any = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Fan out `MEAL_EVENT_REMINDER` for a single meal event.

    Sends one push per accepted participant (plus owner fallback). Each
    `send_to_user` independently consults the recipient's category
    prefs + quiet hours — suppression is per-recipient, not per-event.

    Returns a summary `{"sent": N, "suppressed": M, "attempted": K}`.
    Errors from individual sends are logged but never raised — one bad
    recipient can't kill the batch. The caller (scheduler task) is
    responsible for writing `last_reminder_sent_at` and committing.

    `db_session` is forwarded to `send_to_user` so invalid-token
    cleanup can run.
    """
    now = now or datetime.now(timezone.utc)

    recipients = _resolve_recipients(meal_event)
    if not recipients:
        logger.info(
            "meal_event_reminder: no recipients meal_event_id=%s",
            getattr(meal_event, "id", "?"),
        )
        return {"sent": 0, "suppressed": 0, "attempted": 0}

    is_shared = bool(getattr(meal_event, "is_shared", False))
    recipe = getattr(meal_event, "recipe", None)
    recipe_name = getattr(recipe, "name", None) if recipe is not None else None
    image_url = getattr(recipe, "image_url", None) if recipe is not None else None

    meal_type = getattr(meal_event, "meal_type", "") or ""
    scheduled_at = getattr(meal_event, "scheduled_at", None)
    minutes_until = (
        _minutes_until(now, scheduled_at) if scheduled_at is not None else 0
    )

    push_service = get_push_service()

    sent = 0
    suppressed = 0
    for recipient in recipients:
        partner_name = (
            _partner_first_name(recipient, recipients) if is_shared else None
        )
        title, body = _meal_event_reminder_copy(
            meal_type=meal_type,
            recipe_name=recipe_name,
            minutes_until=minutes_until,
            is_shared=is_shared and partner_name is not None,
            partner_name=partner_name,
        )

        notification = PushNotification(
            title=title,
            body=body,
            notification_type=NotificationType.MEAL_EVENT_REMINDER,
            image_url=image_url,
            data={
                "meal_event_id": str(getattr(meal_event, "id", "")),
                "meal_event_title": getattr(meal_event, "title", "") or "",
                "meal_type": meal_type,
            },
        )

        try:
            result = push_service.send_to_user(
                recipient, notification, db_session, force=False
            )
        except Exception:  # noqa: BLE001 — one bad recipient ≠ skip the rest
            logger.exception(
                "meal_event_reminder: send_to_user raised for "
                "meal_event_id=%s user_id=%s",
                getattr(meal_event, "id", "?"),
                getattr(recipient, "id", "?"),
            )
            continue

        if result.get("success_count", 0) > 0:
            sent += 1
        elif (
            result.get("suppressed_by_prefs")
            or result.get("suppressed_by_category")
            or result.get("suppressed_by_quiet_hours")
        ):
            suppressed += 1

    return {"sent": sent, "suppressed": suppressed, "attempted": len(recipients)}


def notify_meal_event_updated(
    meal_event: Any,
    actor: Any,
    *,
    changed_fields: list[str] | None = None,
    new_time: str | None = None,
    db_session: Any = None,
) -> dict[str, int]:
    """Fan out `MEAL_EVENT_UPDATED` to every accepted participant except
    the actor. Called from the PATCH meal_event endpoint when a
    significant field on a shared event changes (title, scheduled_at,
    recipe_id, meal_id, meal_reminder_time).

    `changed_fields` is used only to pick the copy variant — "only
    scheduled_at changed" → time-specific title; anything else → generic.

    Returns `{"sent": N, "suppressed": M, "attempted": K}`.
    """
    changed_fields = changed_fields or []
    recipients = _resolve_recipients(meal_event)

    actor_id = str(getattr(actor, "id", ""))
    recipients = [r for r in recipients if str(getattr(r, "id", "")) != actor_id]

    if not recipients:
        return {"sent": 0, "suppressed": 0, "attempted": 0}

    only_time_changed = changed_fields == ["scheduled_at"]
    actor_name = _resolve_actor_name(actor)
    event_title = getattr(meal_event, "title", "") or ""

    title, body = _meal_event_updated_copy(
        actor_name=actor_name,
        event_title=event_title,
        scheduled_at_changed=only_time_changed,
        new_time=new_time if only_time_changed else None,
    )

    recipe = getattr(meal_event, "recipe", None)
    image_url = getattr(recipe, "image_url", None) if recipe is not None else None

    notification = PushNotification(
        title=title,
        body=body,
        notification_type=NotificationType.MEAL_EVENT_UPDATED,
        image_url=image_url,
        data={
            "meal_event_id": str(getattr(meal_event, "id", "")),
            "meal_event_title": event_title,
            "actor_id": actor_id,
            "actor_name": actor_name,
        },
    )

    push_service = get_push_service()

    sent = 0
    suppressed = 0
    for recipient in recipients:
        try:
            result = push_service.send_to_user(
                recipient, notification, db_session, force=False
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "meal_event_updated: send_to_user raised for "
                "meal_event_id=%s user_id=%s",
                getattr(meal_event, "id", "?"),
                getattr(recipient, "id", "?"),
            )
            continue

        if result.get("success_count", 0) > 0:
            sent += 1
        elif (
            result.get("suppressed_by_prefs")
            or result.get("suppressed_by_category")
            or result.get("suppressed_by_quiet_hours")
        ):
            suppressed += 1

    return {"sent": sent, "suppressed": suppressed, "attempted": len(recipients)}
