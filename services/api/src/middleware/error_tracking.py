"""Error tracking middleware - logs unhandled exceptions and 500 responses to the database."""

import logging
import traceback
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from utils.models.error_log import ErrorLog
from utils.services.database import Database

logger = logging.getLogger(__name__)


class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a request_id and logs server errors to the error_logs table."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Assign a unique request_id
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception as exc:
            # Unhandled exception - log it and re-raise
            self._log_error(
                request=request,
                request_id=request_id,
                error=exc,
                status_code=500,
            )
            raise

        # Check for 500-level responses
        if response.status_code >= 500:
            self._log_error(
                request=request,
                request_id=request_id,
                error=None,
                status_code=response.status_code,
            )

        return response

    def _log_error(
        self,
        request: Request,
        request_id: str,
        error: Exception | None,
        status_code: int,
    ) -> None:
        """Persist an error record using a fresh database session."""
        try:
            # Extract user_id from request state if available
            user_id = None
            if hasattr(request.state, "user") and request.state.user:
                user_id = getattr(request.state.user, "id", None)

            error_type = type(error).__name__ if error else "HTTP500"
            error_message = str(error) if error else f"Server returned {status_code}"
            stack_trace = traceback.format_exc() if error else None

            database = Database()
            try:
                error_log = ErrorLog(
                    error_type=error_type,
                    error_message=error_message[:4000] if error_message else "",
                    stack_trace=stack_trace,
                    method=request.method[:10] if request.method else None,
                    path=str(request.url.path)[:2000] if request.url else None,
                    status_code=status_code,
                    user_id=user_id,
                    service="api",
                    request_id=request_id,
                )
                database.create(error_log)
            finally:
                database.close()
        except Exception:
            # Never let error tracking break the request
            logger.exception("Failed to log error to error_logs table")
