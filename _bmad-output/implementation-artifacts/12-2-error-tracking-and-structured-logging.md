# Story 12.2: Error Tracking & Structured Logging

**Status:** in-progress

## Summary

Add application error tracking via an `error_logs` database table, middleware to capture unhandled 500 errors, endpoint-level error logging, and a periodic cleanup task.

## Changes

### New Files
- `libraries/utils/utils/models/error_log.py` - ErrorLog SQLAlchemy model
- `services/migrator/migrations/versions/20260409000001_create_error_logs.py` - Alembic migration
- `services/api/src/middleware/__init__.py` - Middleware package init
- `services/api/src/middleware/error_tracking.py` - ErrorTrackingMiddleware (assigns request_id, logs 500s)
- `libraries/utils/utils/tasks/admin_tasks/__init__.py` - Admin tasks package init
- `libraries/utils/utils/tasks/admin_tasks/cleanup_error_logs.py` - Celery beat task to delete logs older than 30 days

### Modified Files
- `libraries/utils/utils/models/__init__.py` - Added ErrorLog import and __all__ entry
- `libraries/utils/utils/db/models.py` - Added ErrorLog import and __all__ entry
- `services/migrator/migrations/env.py` - Added ErrorLog import
- `services/api/src/main.py` - Added ErrorTrackingMiddleware before CORSMiddleware
- `libraries/utils/utils/api/endpoint.py` - Added `_log_error_to_db()` in Endpoint.run() catch block
- `libraries/utils/utils/services/celery.py` - Added cleanup-error-logs beat schedule entry

## Acceptance Criteria
- [x] ErrorLog model with all required columns and indexes
- [x] Alembic migration creates error_logs table
- [x] Middleware assigns request_id and logs 500 errors
- [x] Endpoint.run() logs unhandled exceptions to error_logs
- [x] Cleanup task deletes records older than 30 days
- [x] Celery beat schedule includes cleanup task
- [ ] All existing tests pass
