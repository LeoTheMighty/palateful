"""Morning-of shopping-deadline reminders.

Beat fires this task every 5 min (see `celery.py`). On each tick we:

  1. Bucket users by timezone (`notification_preferences->>timezone`).
     Users with no tz set are skipped — explicit opt-in.
  2. For each tz whose wall-clock is currently in `[08:00, 08:05)`, load
     the users in that tz and look for shopping lists they own or are
     active members of that have unchecked items with `due_at::date ==
     today (in that tz)`.
  3. For each (user, list) pair, upsert a
     `ShoppingListUserReminderState` row and only fire the push when
     the last-sent date (in the user's tz) is strictly less than
     today-in-tz. Each (user, list) is wrapped in try/except so one
     bad row doesn't kill the batch.

Per-user-per-list idempotency is key. Shared lists span users in
different timezones; a shared column on `shopping_lists` would have one
user silence the other (see party-mode review in
epic-notifications-scheduled-reminders).
"""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, or_, select

from utils.api.endpoint import success
from utils.models.shopping_list import ShoppingList, ShoppingListItem
from utils.models.shopping_list_user import ShoppingListUser
from utils.models.shopping_list_user_reminder_state import (
    ShoppingListUserReminderState,
)
from utils.models.user import User
from utils.services.celery import celery_app
from utils.services.shopping_notifications import (
    notify_shopping_deadline_reminder,
)
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Morning window. Beat fires every 5 min so exactly one tick per tz per
# day lands in this window. `[08:00, 08:05)` is a half-open interval —
# a tick at exactly 08:05 belongs to the next window (which never
# matches since it's [08:05, 08:10) and so on).
_REMINDER_HOUR = 8
_REMINDER_WINDOW_MINUTES = 5


def _extract_user_timezone(user: User) -> str | None:
    """Pull the user's timezone from `notification_preferences`.

    Returns None when the field is absent or malformed. Callers skip
    users with no tz (explicit opt-in) so they never get a push at an
    unexpected wall-clock time.
    """
    prefs = user.notification_preferences or {}
    if not isinstance(prefs, dict):
        return None
    tz = prefs.get("timezone")
    if isinstance(tz, str) and tz.strip():
        return tz.strip()
    return None


def _tz_is_in_window(tz_name: str, now_utc: datetime) -> bool:
    """True when wall-clock in `tz_name` falls in [08:00, 08:05)."""
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    local = now_utc.astimezone(tz)
    if local.hour != _REMINDER_HOUR:
        return False
    return local.minute < _REMINDER_WINDOW_MINUTES


def _today_in_tz(tz_name: str, now_utc: datetime):
    """Return the local calendar date (not datetime) for `tz_name`."""
    return now_utc.astimezone(ZoneInfo(tz_name)).date()


class DeadlineReminderTask(BaseTask):
    """Celery beat task — morning-of shopping-deadline summary push."""

    name = "shopping_list_deadline_reminder"

    def execute(self):  # noqa: C901 — the inner loops are intentional
        now_utc = datetime.now(UTC)

        users_processed = 0
        pushes_fired = 0
        errors = 0

        for tz_name in self._candidate_timezones():
            if not _tz_is_in_window(tz_name, now_utc):
                continue

            today = _today_in_tz(tz_name, now_utc)
            users = self._users_in_timezone(tz_name)

            for user in users:
                users_processed += 1
                try:
                    fired = self._process_user(user, tz_name, today, now_utc)
                    pushes_fired += fired
                except Exception:
                    errors += 1
                    logger.exception(
                        "deadline_reminder: failed processing user=%s",
                        user.id,
                    )

        logger.info(
            "deadline_reminder: tick complete users=%d pushes=%d errors=%d",
            users_processed,
            pushes_fired,
            errors,
        )

        return success({
            "users_processed": users_processed,
            "pushes_fired": pushes_fired,
            "errors": errors,
        })

    # ------------------------------------------------------------------
    # Step 1: candidate timezones (one DISTINCT query per tick)
    # ------------------------------------------------------------------
    def _candidate_timezones(self) -> list[str]:
        """DISTINCT non-empty `notification_preferences.timezone` values.

        We pull the raw JSONB key via `->>` to let Postgres do the work
        — no need to hydrate every user row just to read their tz.
        """
        stmt = select(
            func.distinct(
                func.nullif(
                    User.notification_preferences["timezone"].astext,
                    "",
                )
            )
        ).where(
            User.notification_preferences["timezone"].astext.isnot(None)
        )
        rows = self.database.db.execute(stmt).all()
        return [row[0] for row in rows if row[0]]

    # ------------------------------------------------------------------
    # Step 2: users in the in-window timezone
    # ------------------------------------------------------------------
    def _users_in_timezone(self, tz_name: str) -> list[User]:
        return (
            self.database.db.query(User)
            .filter(
                User.notification_preferences["timezone"].astext == tz_name,
                User.archived_at.is_(None),
            )
            .all()
        )

    # ------------------------------------------------------------------
    # Step 3: per-user fan-out over their due-today lists
    # ------------------------------------------------------------------
    def _process_user(
        self,
        user: User,
        tz_name: str,
        today,
        now_utc: datetime,
    ) -> int:
        pushes_fired = 0
        list_due_counts = self._due_today_counts_for_user(user, tz_name, today)

        for shopping_list_id, item_count in list_due_counts.items():
            try:
                fired = self._maybe_fire_for_list(
                    user=user,
                    shopping_list_id=shopping_list_id,
                    item_count=item_count,
                    today=today,
                    tz_name=tz_name,
                    now_utc=now_utc,
                )
                pushes_fired += fired
            except Exception:
                logger.exception(
                    "deadline_reminder: failed user=%s list=%s",
                    user.id,
                    shopping_list_id,
                )
        return pushes_fired

    def _due_today_counts_for_user(
        self, user: User, tz_name: str, today
    ) -> dict:
        """Return {shopping_list_id: unchecked_due_today_count} for `user`.

        Includes lists the user owns OR is an active (non-archived)
        member of. Dedup by list id; the count is the number of items
        whose `due_at::date (in user tz)` == today and `is_checked` is
        false.
        """
        accessible_list_ids = select(ShoppingList.id).where(
            or_(
                ShoppingList.owner_id == user.id,
                ShoppingList.id.in_(
                    select(ShoppingListUser.shopping_list_id).where(
                        ShoppingListUser.user_id == user.id,
                        ShoppingListUser.archived_at.is_(None),
                    )
                ),
            )
        )

        # Render `due_at` in the user's timezone, then truncate to date.
        due_local_date = func.date(
            func.timezone(tz_name, ShoppingListItem.due_at)
        )

        stmt = (
            select(
                ShoppingListItem.shopping_list_id,
                func.count(ShoppingListItem.id),
            )
            .where(
                ShoppingListItem.shopping_list_id.in_(accessible_list_ids),
                ShoppingListItem.is_checked.is_(False),
                ShoppingListItem.due_at.isnot(None),
                due_local_date == today,
            )
            .group_by(ShoppingListItem.shopping_list_id)
        )

        rows = self.database.db.execute(stmt).all()
        return {row[0]: row[1] for row in rows if row[1] > 0}

    def _maybe_fire_for_list(
        self,
        *,
        user: User,
        shopping_list_id,
        item_count: int,
        today,
        tz_name: str,
        now_utc: datetime,
    ) -> int:
        """Check state-row idempotency, fire if appropriate, update state."""
        state = (
            self.database.db.query(ShoppingListUserReminderState)
            .filter_by(
                user_id=user.id, shopping_list_id=shopping_list_id
            )
            .one_or_none()
        )

        if state is None:
            state = ShoppingListUserReminderState(
                user_id=user.id,
                shopping_list_id=shopping_list_id,
                last_deadline_reminder_sent_at=None,
            )
            self.database.db.add(state)

        if state.last_deadline_reminder_sent_at is not None:
            last_local_date = (
                state.last_deadline_reminder_sent_at
                .astimezone(ZoneInfo(tz_name))
                .date()
            )
            if last_local_date >= today:
                return 0

        shopping_list = self.database.find_by(
            ShoppingList, id=shopping_list_id
        )
        if shopping_list is None:
            return 0

        notify_shopping_deadline_reminder(
            self.database,
            user=user,
            shopping_list=shopping_list,
            item_count=item_count,
        )

        state.last_deadline_reminder_sent_at = now_utc
        self.database.db.commit()
        return 1


# Register the task with Celery
deadline_reminder_task = celery_app.register_task(DeadlineReminderTask())
