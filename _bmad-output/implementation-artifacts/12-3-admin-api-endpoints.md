# Story 12.3: Admin API Endpoints

**Status:** in-progress

## Summary

Create admin-only API endpoints for log viewing, error tracking, user management, and dashboard stats, all protected by `require_admin` dependency.

## Changes

### New Files
- `services/api/src/api/v1/admin/__init__.py` - Admin endpoint package init with exports
- `services/api/src/api/v1/admin/get_logs.py` - GetLogs endpoint (CloudWatch proxy)
- `services/api/src/api/v1/admin/get_errors.py` - GetErrors endpoint (error_logs list)
- `services/api/src/api/v1/admin/get_error_detail.py` - GetErrorDetail endpoint (single error with stack trace)
- `services/api/src/api/v1/admin/list_users.py` - ListUsers endpoint (all users with pagination)
- `services/api/src/api/v1/admin/update_user_admin.py` - UpdateUserAdmin endpoint (toggle is_admin)
- `services/api/src/api/v1/admin/get_stats.py` - GetStats endpoint (dashboard aggregate counts)
- `services/api/src/routers/v1/admin_router.py` - Admin router with all endpoints wired

### Modified Files
- `services/api/src/routers/v1_router.py` - Added admin_router import and include

## Acceptance Criteria
- [x] All endpoints protected by `require_admin` dependency
- [x] GET /v1/admin/logs proxies to CloudWatch with friendly error for local dev
- [x] GET /v1/admin/errors lists errors with pagination
- [x] GET /v1/admin/errors/{error_id} returns full error detail with stack trace
- [x] GET /v1/admin/users lists all users with pagination
- [x] PUT /v1/admin/users/{user_id}/admin toggles admin status with last-admin safety check
- [x] GET /v1/admin/stats returns aggregate dashboard counts
- [x] Router wired into v1_router
