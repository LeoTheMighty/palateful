"""Get error detail endpoint."""

from pydantic import BaseModel
from sqlalchemy import select
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.error_log import ErrorLog


class GetErrorDetail(AsyncEndpoint):
    """Fetch a single error log by ID."""

    async def execute(self, error_id: str):
        """Get full error detail including stack trace."""
        error = (await self.db.execute(
            select(ErrorLog).where(ErrorLog.id == error_id)
        )).scalar_one_or_none()

        if not error:
            raise APIException(
                status_code=404,
                detail="Error log not found",
                code=ErrorCode.NOT_FOUND,
            )

        return success(
            data=GetErrorDetail.Response(
                id=str(error.id),
                error_type=error.error_type,
                error_message=error.error_message,
                stack_trace=error.stack_trace,
                error_code=error.error_code,
                method=error.method,
                path=error.path,
                status_code=error.status_code,
                user_id=str(error.user_id) if error.user_id else None,
                service=error.service,
                created_at=error.created_at.isoformat() if error.created_at else None,
                request_id=error.request_id,
            )
        )

    class Response(BaseModel):
        """Response model."""

        id: str
        error_type: str
        error_message: str
        stack_trace: str | None = None
        error_code: int | None = None
        method: str | None = None
        path: str | None = None
        status_code: int | None = None
        user_id: str | None = None
        service: str
        created_at: str | None = None
        request_id: str | None = None
