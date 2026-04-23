"""Nightly prune task for the latency sample tables.

Keeps `request_latencies`, `task_latencies`, and `client_latencies`
(cla-1a) bounded at 30 days of history. Runs at the 02:00 UTC slot
alongside the existing `cleanup_error_logs` task. See
`docs/OBSERVABILITY.md` for the escalation path if combined table
size ever crosses ~2 GB (tighten to 14 d before any partitioning
work).

Monthly VACUUM — the `client_latencies` table is the fastest-growing
of the three (~125k rows/day vs a few thousand for the others per
the capacity math in `epic-perf-client-analytics.md`). On the 1st of
each month we run `VACUUM ANALYZE` on all three tables to reclaim
space from the daily deletes and refresh the planner's row-count
estimates (which autovacuum keeps roughly right but lags behind
large batch deletes). Runs outside any transaction.
"""

import logging
from datetime import datetime, timedelta

from utils.api.endpoint import success
from utils.models.client_latency import ClientLatency
from utils.models.request_latency import RequestLatency
from utils.models.task_latency import TaskLatency
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)

# Retention constant lives here (not in `constants.py`) so changing the
# retention window is a one-file edit alongside the task's
# documentation / runbook entry.
RETENTION_DAYS = 30

# Tables swept nightly and VACUUMed monthly.
_VACUUM_TABLES = ("request_latencies", "task_latencies", "client_latencies")


class CleanupLatencySamplesTask(BaseTask):
    """Delete latency sample rows older than 30 days across all three tables.

    Idempotent — running twice in the same night is a no-op after the
    first run deletes the matching rows. Uses `synchronize_session=False`
    since this task never reads the rows it deletes.

    On the 1st of each month the task also issues `VACUUM ANALYZE` on
    each of the three tables. VACUUM cannot run inside a transaction,
    so the call is routed through a raw-connection autocommit block.
    """

    name = "cleanup_latency_samples"

    def execute(self):
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)

        request_count = self._prune(RequestLatency, cutoff, "request_latencies")
        task_count = self._prune(TaskLatency, cutoff, "task_latencies")
        client_count = self._prune(ClientLatency, cutoff, "client_latencies")

        vacuum_ran = False
        if datetime.utcnow().day == 1:
            self._vacuum_analyze_all()
            vacuum_ran = True

        return success({
            "request_deleted_count": request_count,
            "task_deleted_count": task_count,
            "client_deleted_count": client_count,
            "vacuum_ran": vacuum_ran,
        })

    def _prune(self, model, cutoff, table_name: str) -> int:
        """Delete rows older than cutoff; return the count deleted."""
        query = (
            self.database.db.query(model)
            .filter(model.created_at < cutoff)
        )
        count = query.count()
        if count > 0:
            query.delete(synchronize_session=False)
            self.database.db.commit()
            logger.info(
                "Deleted %d %s rows older than %d days",
                count, table_name, RETENTION_DAYS,
            )
        else:
            logger.info(
                "No %s rows older than %d days to delete",
                table_name, RETENTION_DAYS,
            )
        return count

    def _vacuum_analyze_all(self) -> None:
        """Issue `VACUUM ANALYZE` on each latency table.

        VACUUM cannot run inside a transaction block — acquire a raw
        psycopg connection, flip to autocommit, run the statement,
        restore. One round-trip per table; total runtime in the
        seconds range at current scale.
        """
        engine = self.database.db.get_bind()
        conn = engine.raw_connection()
        try:
            prior_isolation = conn.isolation_level
            conn.set_isolation_level(0)  # AUTOCOMMIT
            cur = conn.cursor()
            for table in _VACUUM_TABLES:
                cur.execute(f"VACUUM ANALYZE {table}")
                logger.info("VACUUM ANALYZE %s complete", table)
            cur.close()
            conn.set_isolation_level(prior_isolation)
        finally:
            conn.close()


# Register the task with Celery.
cleanup_latency_samples_task = celery_app.register_task(CleanupLatencySamplesTask())
