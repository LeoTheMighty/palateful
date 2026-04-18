"""Admin endpoints router."""

from api.v1.admin import (
    GetEndpointMetrics,
    GetErrorDetail,
    GetErrors,
    GetLogs,
    GetStats,
    GetTaskMetrics,
    ListFeedback,
    ListUsers,
    SendTestPush,
    UpdateFeedbackStatus,
    UpdateUserAdmin,
)
from dependencies import get_database, require_admin
from fastapi import APIRouter, Depends, Query
from utils.models.user import User
from utils.services.database import Database

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/logs")
async def get_logs(
    service: str = Query("api", description="Service name (api or worker)"),
    level: str | None = Query(None, description="Log level filter"),
    search: str | None = Query(None, description="Search text filter"),
    start_time: int | None = Query(None, description="Start time (epoch ms)"),
    end_time: int | None = Query(None, description="End time (epoch ms)"),
    limit: int = Query(100, ge=1, le=500, description="Max events to return"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Get CloudWatch logs for a service."""
    return GetLogs.call(
        service=service,
        level=level,
        search=search,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        user=user,
        database=database,
    )


@admin_router.get("/errors")
async def get_errors(
    service: str | None = Query(None, description="Filter by service"),
    limit: int = Query(50, ge=1, le=200, description="Max errors to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """List error logs."""
    return GetErrors.call(
        service=service,
        limit=limit,
        offset=offset,
        user=user,
        database=database,
    )


@admin_router.get("/errors/{error_id}")
async def get_error_detail(
    error_id: str,
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Get a single error log with full details."""
    return GetErrorDetail.call(
        error_id=error_id,
        user=user,
        database=database,
    )


@admin_router.get("/users")
async def list_users(
    limit: int = Query(50, ge=1, le=200, description="Max users to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """List all users."""
    return ListUsers.call(
        limit=limit,
        offset=offset,
        user=user,
        database=database,
    )


@admin_router.put("/users/{user_id}/admin")
async def update_user_admin(
    user_id: str,
    params: UpdateUserAdmin.Params,
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Toggle admin status for a user."""
    return UpdateUserAdmin.call(
        user_id=user_id,
        params=params,
        user=user,
        database=database,
    )


@admin_router.get("/stats")
async def get_stats(
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Get dashboard statistics."""
    return GetStats.call(
        user=user,
        database=database,
    )


@admin_router.post("/notifications/test-push")
async def send_test_push(
    params: SendTestPush.Params,
    force: bool = Query(True, description="Bypass quiet hours (default true)"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Fire a test FCM push to verify the round-trip."""
    return SendTestPush.call(
        params=params,
        force=force,
        user=user,
        database=database,
    )


# ============================================================
# Feedback Inbox
# ============================================================


@admin_router.get("/feedback")
async def list_feedback(
    status: str = Query("unread", description="Filter by status: unread | read | archived | all"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(25, ge=1, le=100, description="Max items per page"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """List feedback entries for the admin inbox."""
    return ListFeedback.call(
        status=status,
        offset=offset,
        limit=limit,
        user=user,
        database=database,
    )


@admin_router.put("/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    params: UpdateFeedbackStatus.Params,
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Flip the status of a single feedback row (unread/read/archived)."""
    return UpdateFeedbackStatus.call(
        feedback_id=feedback_id,
        params=params,
        user=user,
        database=database,
    )


# ============================================================
# Operator Observability — Latency Metrics (obs-latency-2)
# ============================================================


@admin_router.get("/metrics/endpoints")
async def get_endpoint_metrics(
    window: str = Query("24h", description="Window: 1h | 24h | 7d"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Percentile + sparkline per (method, normalized_path)."""
    return GetEndpointMetrics.call(
        window=window,
        user=user,
        database=database,
    )


@admin_router.get("/metrics/tasks")
async def get_task_metrics(
    window: str = Query("24h", description="Window: 1h | 24h | 7d"),
    user: User = Depends(require_admin),
    database: Database = Depends(get_database),
):
    """Percentile + sparkline per Celery task_name."""
    return GetTaskMetrics.call(
        window=window,
        user=user,
        database=database,
    )
