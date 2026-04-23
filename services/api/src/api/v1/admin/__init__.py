"""Admin endpoint implementations."""

from api.v1.admin.get_client_metrics import (
    GetClientEndpointMetrics,
    GetClientJankMetrics,
    GetClientRouteMetrics,
    GetClientSparkline,
)
from api.v1.admin.get_endpoint_metrics import GetEndpointMetrics
from api.v1.admin.get_error_detail import GetErrorDetail
from api.v1.admin.get_errors import GetErrors
from api.v1.admin.get_logs import GetLogs
from api.v1.admin.get_push_health import GetAdminPushHealth
from api.v1.admin.get_stats import GetStats
from api.v1.admin.get_task_metrics import GetTaskMetrics
from api.v1.admin.list_feedback import ListFeedback
from api.v1.admin.list_users import ListUsers
from api.v1.admin.send_test_push import SendTestPush
from api.v1.admin.update_feedback_status import UpdateFeedbackStatus
from api.v1.admin.update_user_admin import UpdateUserAdmin

__all__ = [
    "GetAdminPushHealth",
    "GetClientEndpointMetrics",
    "GetClientJankMetrics",
    "GetClientRouteMetrics",
    "GetClientSparkline",
    "GetEndpointMetrics",
    "GetErrorDetail",
    "GetErrors",
    "GetLogs",
    "GetStats",
    "GetTaskMetrics",
    "ListFeedback",
    "ListUsers",
    "SendTestPush",
    "UpdateFeedbackStatus",
    "UpdateUserAdmin",
]
