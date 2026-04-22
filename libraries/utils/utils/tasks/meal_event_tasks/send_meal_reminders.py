"""Celery beat task: fire `MEAL_EVENT_REMINDER` for meals whose
resolved reminder-time falls inside the current 5-minute window.

Cadence (from celery beat): every 5 minutes. A meal is picked up if:

  - `scheduled_at::date` is today in the meal-owner's timezone;
  - The resolved reminder time (`meal_reminder_time` or slot default)
    in the owner's local time falls inside `[now, now + 5min]`;
  - `last_reminder_sent_at` is NULL or strictly older than "today's
    window start" (recurring-meal instances are materialized as
    separate rows, so a per-row `last_reminder_sent_at` is enough);
  - `status` is not `completed` or `skipped`.

Per-recipient fan-out: `notify_meal_event_reminder` in
`utils.services.meal_event_notifications` iterates accepted
participants (+ owner fallback), calling `send_to_user` which applies
per-user category prefs + quiet hours. Recipient timezone governs the
wall-clock moment for quiet-hours, but the *scheduler* uses the
meal-owner's timezone to decide *when* to fire — simpler than
resolving each participant's local time inside the task scan.

Worst-case lag: 5 min (beat cadence). Acceptable per UX — the user
picks a wall-clock minute, not a nanosecond. Log `logger.exception`
per-event; one bad event doesn't kill the batch.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from utils.api.endpoint import success
from utils.models.error_log import ErrorLog
from utils.models.meal_event import MEAL_SLOT_DEFAULT_TIMES, MealEvent
from utils.services.celery import celery_app
from utils.services.meal_event_notifications import notify_meal_event_reminder
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Beat cadence in seconds. Scan window is [now, now + BEAT_WINDOW_SECONDS).
# Must match the schedule entry in `utils.services.celery.celery_app.conf
# .beat_schedule["send-meal-reminders"]`.
BEAT_WINDOW_SECONDS = 300  # 5 min

# Skip events in terminal states — nobody wants a "Dinner in 5 —
# Carbonara" ping for a meal they already marked completed.
_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "skipped"})


def _owner_timezone(meal_event: MealEvent) -> ZoneInfo:
    """Resolve the meal owner's IANA tz, defaulting to UTC on any lookup
    miss. The prefs default is `America/Denver`, but safe-default UTC
    means a malformed pref won't explode the batch scan."""
    owner = getattr(meal_event, "owner", None)
    if owner is None:
        return ZoneInfo("UTC")
    prefs = getattr(owner, "notification_preferences", None) or {}
    tz_name = prefs.get("timezone") if isinstance(prefs, dict) else None
    if not tz_name or not isinstance(tz_name, str):
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 — unknown tz string
        return ZoneInfo("UTC")


def _resolve_reminder_moment(
    meal_event: MealEvent,
    owner_tz: ZoneInfo,
) -> datetime | None:
    """Combine the event's local date + the resolved reminder time into
    a timezone-aware UTC datetime. Returns None when the event has no
    `scheduled_at` (shouldn't happen in prod — column is NOT NULL, but
    defensive for tests)."""
    scheduled_at: datetime | None = getattr(meal_event, "scheduled_at", None)
    if scheduled_at is None:
        return None

    # Local date in the owner's tz — DST transitions are the OS's
    # responsibility (zoneinfo).
    local_date: date = scheduled_at.astimezone(owner_tz).date()

    resolved_time: time = (
        meal_event.meal_reminder_time
        if meal_event.meal_reminder_time is not None
        else MEAL_SLOT_DEFAULT_TIMES.get(
            meal_event.meal_type, MEAL_SLOT_DEFAULT_TIMES["lunch"]
        )
    )

    local_dt = datetime.combine(local_date, resolved_time, tzinfo=owner_tz)
    return local_dt.astimezone(timezone.utc)


def _should_fire(
    meal_event: MealEvent,
    now: datetime,
    window_end: datetime,
) -> bool:
    """Decide whether a candidate event should push this tick.

    Three gates beyond the SQL filter:
      1. Terminal status → skip.
      2. Resolved reminder moment must fall in [now, window_end).
      3. Idempotency: `last_reminder_sent_at` must be NULL or strictly
         before `now` (i.e. not fired in a prior 5-min tick).
    """
    if meal_event.status in _TERMINAL_STATUSES:
        return False

    owner_tz = _owner_timezone(meal_event)
    reminder_at = _resolve_reminder_moment(meal_event, owner_tz)
    if reminder_at is None:
        return False

    if reminder_at < now or reminder_at >= window_end:
        return False

    last_sent: datetime | None = getattr(meal_event, "last_reminder_sent_at", None)
    if last_sent is not None and last_sent >= now:
        # Already fired in a later-or-equal tick — dedupe.
        return False

    return True


def _log_task_failure(database: Any, meal_event_id: str, detail: str) -> None:
    """Write an `error_logs` row for one-event failures so the batch
    keeps going but the failure is queryable from the audit script."""
    try:
        err = ErrorLog(
            error_type="MealReminderTaskError",
            error_message=f"send_meal_reminders: meal_event_id={meal_event_id}: {detail[:500]}",
            service="push_notifications",
        )
        database.create(err)
    except Exception:  # noqa: BLE001
        logger.exception("send_meal_reminders: failed to write error_log row")


class SendMealRemindersTask(BaseTask):
    """Periodic fan-out of meal-time reminders.

    Idempotent: re-running mid-window finds `last_reminder_sent_at`
    populated for any event already pushed and skips it. The column is
    set AFTER `notify_meal_event_reminder` returns for a given event,
    so a crash mid-fan-out will re-send on the next tick (at-least-once;
    duplicate pushes are preferable to silent drops).
    """

    name = "send_meal_reminders"

    def execute(self):
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(seconds=BEAT_WINDOW_SECONDS)

        # SQL-level pre-filter: only today's events with a permissive
        # range on `scheduled_at`. The per-row owner-tz math happens in
        # Python (`_should_fire`) — doing it in SQL would require
        # joining users + casting, and the tight time window bounds the
        # row count regardless.
        lower_bound = now - timedelta(days=1)
        upper_bound = window_end + timedelta(days=1)

        candidates = (
            self.database.db.query(MealEvent)
            .filter(MealEvent.scheduled_at >= lower_bound)
            .filter(MealEvent.scheduled_at < upper_bound)
            .filter(~MealEvent.status.in_(list(_TERMINAL_STATUSES)))
            .filter(
                (MealEvent.last_reminder_sent_at.is_(None))
                | (MealEvent.last_reminder_sent_at < now)
            )
            .all()
        )

        total_sent = 0
        total_events = 0
        for event in candidates:
            if not _should_fire(event, now, window_end):
                continue
            total_events += 1
            try:
                result = notify_meal_event_reminder(
                    event, db_session=self.database.db, now=now
                )
                total_sent += result.get("sent", 0)
                # Mark idempotency regardless of send outcome — a
                # per-recipient suppression isn't a retry signal.
                event.last_reminder_sent_at = now
                self.database.db.commit()
            except Exception as exc:  # noqa: BLE001 — don't kill the batch
                logger.exception(
                    "send_meal_reminders: event_id=%s failed", event.id
                )
                self.database.db.rollback()
                _log_task_failure(self.database, str(event.id), repr(exc))

        logger.info(
            "send_meal_reminders: window=%s..%s events_fired=%d pushes_sent=%d",
            now.isoformat(),
            window_end.isoformat(),
            total_events,
            total_sent,
        )
        return success(
            {
                "events_fired": total_events,
                "pushes_sent": total_sent,
                "candidates_scanned": len(candidates),
            }
        )


send_meal_reminders_task = celery_app.register_task(SendMealRemindersTask())
