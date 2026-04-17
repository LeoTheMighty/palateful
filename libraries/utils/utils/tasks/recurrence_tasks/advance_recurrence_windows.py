"""Nightly task: advance the 9-week materialization window for every rule
and archive materialized meal_events older than 6 months.
"""

import logging
from datetime import date, datetime, timedelta

from utils.api.endpoint import success
from utils.models.error_log import ErrorLog
from utils.models.meal_event import MealEvent
from utils.models.meal_recurrence_rule import MealRecurrenceRule
from utils.recurrence.materializer import materialize
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

MATERIALIZATION_WINDOW_WEEKS = 9
ARCHIVE_CUTOFF_DAYS = 180  # ~6 months


def _log_audit(db, message: str, payload: dict | None = None) -> None:
    """Write a row to error_logs with service='worker' as a structured
    audit/observability log. Mirrors the pattern used by promote_admin.py."""
    try:
        body = message
        if payload:
            body = f"{message} {payload}"
        entry = ErrorLog(
            service="worker",
            error_type="audit",
            error_message=body,
        )
        db.add(entry)
        db.commit()
    except Exception:
        logger.exception("Failed to write audit log for: %s", message)


class AdvanceRecurrenceWindowsTask(BaseTask):
    """Walk every active rule, materialize forward 9 weeks, archive old rows.

    Per-rule failures are logged to error_logs (service='worker') and do not
    abort the run. Re-runs are idempotent.
    """

    name = "advance_recurrence_windows"

    def execute(self):
        db = self.database.db
        today = date.today()
        through = today + timedelta(weeks=MATERIALIZATION_WINDOW_WEEKS)

        _log_audit(db, "advance_recurrence_windows:start")

        rules = (
            db.query(MealRecurrenceRule)
            .filter(MealRecurrenceRule.archived_at.is_(None))
            .all()
        )

        rows_touched = 0
        per_rule_failures = 0
        for rule in rules:
            try:
                materialized = materialize(rule, through, db)
                rows_touched += len(materialized)
                db.commit()
            except Exception as exc:
                per_rule_failures += 1
                db.rollback()
                _log_audit(
                    db,
                    f"advance_recurrence_windows:rule_failed rule_id={rule.id}",
                    {"rule_id": str(rule.id), "error": str(exc)},
                )

        archive_cutoff_dt = datetime.utcnow() - timedelta(days=ARCHIVE_CUTOFF_DAYS)
        archived_count = (
            db.query(MealEvent)
            .filter(MealEvent.recurrence_rule_id.isnot(None))
            .filter(MealEvent.scheduled_at < archive_cutoff_dt)
            .filter(MealEvent.archived_at.is_(None))
            .update(
                {MealEvent.archived_at: datetime.utcnow()},
                synchronize_session=False,
            )
        )
        db.commit()

        _log_audit(
            db,
            "advance_recurrence_windows:complete",
            {
                "rule_count": len(rules),
                "rows_touched": rows_touched,
                "archived_count": archived_count,
                "per_rule_failures": per_rule_failures,
            },
        )

        return success(
            {
                "rule_count": len(rules),
                "rows_touched": rows_touched,
                "archived_count": archived_count,
                "per_rule_failures": per_rule_failures,
            }
        )


advance_recurrence_windows_task = celery_app.register_task(
    AdvanceRecurrenceWindowsTask()
)
