"""Cleanup error logs task - deletes error_logs older than 30 days."""

import logging
from datetime import datetime, timedelta

from utils.api.endpoint import success
from utils.models.error_log import ErrorLog
from utils.services.celery import celery_app
from utils.tasks.task import BaseTask

logger = logging.getLogger(__name__)


class CleanupErrorLogsTask(BaseTask):
    """Delete error_logs records older than 30 days.

    Runs periodically via Celery Beat to keep the error_logs table from growing
    indefinitely.
    """

    name = "cleanup_error_logs"

    def execute(self):
        """Delete error log entries older than 30 days.

        Returns:
            Success response with count of deleted records.
        """
        cutoff = datetime.utcnow() - timedelta(days=30)

        query = (
            self.database.db.query(ErrorLog)
            .filter(ErrorLog.created_at < cutoff)
        )
        count = query.count()

        if count > 0:
            query.delete(synchronize_session=False)
            self.database.db.commit()
            logger.info("Deleted %d error_logs older than 30 days", count)
        else:
            logger.info("No error_logs older than 30 days to delete")

        return success({
            "deleted_count": count,
        })


# Register the task with Celery
cleanup_error_logs_task = celery_app.register_task(CleanupErrorLogsTask())
