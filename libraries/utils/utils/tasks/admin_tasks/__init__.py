"""Admin background tasks."""

from utils.tasks.admin_tasks.cleanup_error_logs import CleanupErrorLogsTask

__all__ = [
    "CleanupErrorLogsTask",
]
