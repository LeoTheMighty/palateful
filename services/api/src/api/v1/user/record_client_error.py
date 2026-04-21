"""POST /v1/users/me/client-errors — mirror client-side Crashlytics events into error_logs.

Fire-and-forget sink for the Flutter `ErrorReporter`. Every
`ErrorReporter.report(...)` and `.log(...)` call on device can POST
here so client-side failures land in the same `error_logs` table the
server uses, queryable via `audit_errors.py --service client`.

Tight input envelope (Pydantic extra='forbid') so clients can't
smuggle arbitrary columns. HTTP metadata from DioException mirrors
(`extras['http.method']`, `extras['http.path']`) is hoisted to the
first-class `method`/`path` columns so existing rollups work
unchanged.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ConfigDict, Field
from utils.api.endpoint import Endpoint, success
from utils.models.error_log import ErrorLog
from utils.models.user import User

logger = logging.getLogger(__name__)

_MAX_ERROR_TYPE_LEN = 120
_MAX_MESSAGE_LEN = 2000
_MAX_STACK_LEN = 8000


class RecordClientError(Endpoint):
    """Record a client-side error or breadcrumb into error_logs."""

    def execute(self, params: RecordClientError.Params):
        user: User = self.user

        envelope: dict = {}
        if params.area is not None:
            envelope["area"] = params.area
        if params.operation is not None:
            envelope["operation"] = params.operation
        if params.extras:
            envelope["extras"] = params.extras
        stack_trace = (
            json.dumps(envelope)[:_MAX_STACK_LEN] if envelope else None
        )

        method = None
        path = None
        if params.extras:
            raw_method = params.extras.get("http.method")
            if isinstance(raw_method, str):
                method = raw_method[:10]
            raw_path = params.extras.get("http.path")
            if isinstance(raw_path, str):
                path = raw_path[:500]

        row = ErrorLog(
            error_type=params.error_type[:_MAX_ERROR_TYPE_LEN],
            error_message=params.error_message[:_MAX_MESSAGE_LEN],
            stack_trace=stack_trace,
            service="client",
            user_id=user.id,
            status_code=params.status_code,
            method=method,
            path=path,
        )
        self.db.add(row)
        self.db.commit()

        return success(data=RecordClientError.Response(recorded=True))

    class Params(BaseModel):
        model_config = ConfigDict(extra="forbid")

        error_type: str = Field(min_length=1, max_length=_MAX_ERROR_TYPE_LEN)
        error_message: str = Field(min_length=1, max_length=_MAX_MESSAGE_LEN)
        area: str | None = Field(default=None, max_length=64)
        operation: str | None = Field(default=None, max_length=128)
        extras: dict | None = None
        status_code: int | None = None

    class Response(BaseModel):
        recorded: bool
