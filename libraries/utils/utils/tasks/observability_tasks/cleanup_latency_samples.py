"""Nightly prune task for the latency sample tables.

Keeps `request_latencies` and `task_latencies` bounded at 30 days of
history. Runs at the 02:00 UTC slot alongside the existing
`cleanup_error_logs` task. See `docs/OBSERVABILITY.md` for the
escalation path if combined table size ever crosses ~2 GB (tighten to
14 d before any partitioning work).
"""

import logging
from datetime import datetime, timedelta

from utils.api.endpoint import success
from utils.models.request_latency import RequestLatency
from utils.models.task_latency import TaskLatency
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Retention constant lives here (not in `constants.py`) so changing the
# retention window is a one-file edit alongside the task's
# documentation / runbook entry.
RETENTION_DAYS = 30


class CleanupLatencySamplesTask(BaseTask):
    """Delete request_latencies + task_latencies rows older than 30 days.

    Idempotent — running twice in the same night is a no-op after the
    first run deletes the matching rows. Uses `synchronize_session=False`
    since this task never reads the rows it deletes.
    """

    name = "cleanup_latency_samples"

    def execute(self):
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)

        request_query = (
            self.database.db.query(RequestLatency)
            .filter(RequestLatency.created_at < cutoff)
        )
        request_count = request_query.count()
        if request_count > 0:
            request_query.delete(synchronize_session=False)
            self.database.db.commit()
            logger.info(
                "Deleted %d request_latencies rows older than %d days",
                request_count,
                RETENTION_DAYS,
            )
        else:
            logger.info(
                "No request_latencies rows older than %d days to delete",
                RETENTION_DAYS,
            )

        task_query = (
            self.database.db.query(TaskLatency)
            .filter(TaskLatency.created_at < cutoff)
        )
        task_count = task_query.count()
        if task_count > 0:
            task_query.delete(synchronize_session=False)
            self.database.db.commit()
            logger.info(
                "Deleted %d task_latencies rows older than %d days",
                task_count,
                RETENTION_DAYS,
            )
        else:
            logger.info(
                "No task_latencies rows older than %d days to delete",
                RETENTION_DAYS,
            )

        return success({
            "request_deleted_count": request_count,
            "task_deleted_count": task_count,
        })


# Register the task with Celery.
cleanup_latency_samples_task = celery_app.register_task(CleanupLatencySamplesTask())
