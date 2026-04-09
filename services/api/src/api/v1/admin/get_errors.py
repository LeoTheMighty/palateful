"""Get error logs endpoint."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from utils.api.endpoint import Endpoint, success
from utils.models.error_log import ErrorLog


class GetErrors(Endpoint):
    """List errors from error_logs table."""

    def execute(
        self,
        service: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """Query error_logs ordered by created_at desc."""
        query = select(ErrorLog)

        if service:
            query = query.where(ErrorLog.service == service)

        # Get total count
        count_query = select(func.count()).select_from(ErrorLog)
        if service:
            count_query = count_query.where(ErrorLog.service == service)
        total = self.db.execute(count_query).scalar() or 0

        # Get paginated results
        results = (
            self.db.execute(
                query.order_by(ErrorLog.created_at.desc())
                .limit(min(limit, 200))
                .offset(offset)
            )
            .scalars()
            .all()
        )

        errors = [
            GetErrors.ErrorItem(
                id=str(error.id),
                error_type=error.error_type,
                error_message=error.error_message,
                method=error.method,
                path=error.path,
                status_code=error.status_code,
                service=error.service,
                created_at=error.created_at.isoformat() if error.created_at else None,
                request_id=error.request_id,
            )
            for error in results
        ]

        return success(
            data=GetErrors.Response(
                errors=errors,
                total=total,
            )
        )

    class ErrorItem(BaseModel):
        """A single error log entry (summary)."""

        id: str
        error_type: str
        error_message: str
        method: str | None = None
        path: str | None = None
        status_code: int | None = None
        service: str
        created_at: str | None = None
        request_id: str | None = None

    class Response(BaseModel):
        """Response model."""

        errors: list["GetErrors.ErrorItem"]
        total: int
