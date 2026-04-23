"""Endpoint base class for FastAPI routes."""

import json
import logging
import traceback
import typing

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from utils.classes.error_code import ErrorCode
from utils.constants import LOGGING_LEVEL
from utils.services.helpers.encoder import CustomEncoder

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)


class CustomJSONResponse(JSONResponse):
    """Custom JSON response object to allow our custom encoder to serialize endpoint results."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=CustomEncoder
        ).encode("utf-8")


class APIException(Exception):
    """Custom exception with error codes for API endpoints."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code.value if isinstance(code, ErrorCode) else code

    def __str__(self):
        return f"APIException(code={self.code}): {self.detail}"


class Endpoint:
    """
    Endpoint parent class to define all endpoints.

    Example Implementation:
    ```
    class Example(Endpoint):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # More setup if necessary like connecting to AWS resources

        def execute(self, params: 'Example.Params'):
            # Do the endpoint stuff
            return success(Example.Response(**{ 'success': True }))

        class Params(BaseModel):
            param1: str
            param2: int

        class Response(BaseModel):
            success: bool
    ```

    Example Usage:
    ```
    @example_router.post("/", response_model=Example.Response)
    async def example_endpoint(
        example_input: Example.Params,
        db: Session = Depends(get_db)
    ):
        return Example.call(
            example_input,
            db=db
        )
    ```
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.db = kwargs.pop("db", None)
        self.database = kwargs.pop("database", None)
        if self.database is not None:
            self.db = self.database.db
        # Capture the FastAPI request object
        self.request = kwargs.pop("request", None)
        # Store user if passed
        self.user = kwargs.pop("user", None)
        self.kwargs = kwargs

    @classmethod
    def call(cls, *args, **kwargs):
        """Calls the endpoint execute, then handles the result"""
        return cls.handle_result(cls(*args, **kwargs).run())

    @classmethod
    def handle_result(cls, result):
        """Handles the result of the endpoint, handling output responses"""
        if result['success']:
            return CustomJSONResponse(
                content=jsonable_encoder(result['data']),
                status_code=result['status'],
                headers=result.get('headers') or None,
            )
        # Log error
        if result.get('error'):
            logger.exception(result['error'])
        return CustomJSONResponse(
            content={
                'error_code': result['error_code'],
                'error_message': result['error_message'],
                'data': result.get('data', {}),
            },
            status_code=result['status'],
        )

    def run(self):
        """Runs the endpoint, handling error handling."""
        args = self.args
        kwargs = self.kwargs

        logger.debug("Endpoint %s - Args: %s, Kwargs: %s",
                     self.__class__.__name__, args, kwargs)

        try:
            logger.info("Executing endpoint: %s", self.__class__.__name__)
            result = self.execute(*args, **kwargs)

            if endpoint_result_is_valid(result):
                return result
            raise APIException(
                status_code=500,
                detail=f"Endpoint result not valid. Result: {json.dumps(result, cls=CustomEncoder)}",
                code=ErrorCode.INVALID_ENDPOINT_RESULT
            )
        except APIException as e:
            logger.error("Endpoint %s failed with api error: %s",
                         self.__class__.__name__, str(e), exc_info=True)
            return failure(
                error_code=e.code,
                error_message=e.detail,
                status=e.status_code,
                data={},
                error=e
            )
        except Exception as e:
            logger.error("Endpoint %s failed with error: %s",
                         self.__class__.__name__, str(e), exc_info=True)
            self._log_error_to_db(e)
            return failure(
                data={},
                error_message=str(e),
                error=e
            )

    def _log_error_to_db(self, error: Exception) -> None:
        """Persist an unhandled endpoint error to the error_logs table.

        Uses a separate database session to avoid polluting the request transaction.
        Silently catches any failure so error tracking never breaks the response.
        """
        try:
            from utils.models.error_log import ErrorLog
            from utils.services.database import Database

            stack_trace = traceback.format_exc()

            # Derive request metadata when available
            method = None
            path = None
            request_id = None
            user_id = None

            if self.request:
                method = getattr(self.request, "method", None)
                if method:
                    method = method[:10]
                url = getattr(self.request, "url", None)
                if url:
                    path = str(url.path)[:2000]
                state = getattr(self.request, "state", None)
                if state:
                    request_id = getattr(state, "request_id", None)

            if self.user:
                user_id = getattr(self.user, "id", None)

            # aam-3: prefer the dedicated error-log engine (pool_size=3,
            # max_overflow=2) when available so error logging can never
            # starve behind a main-pool exhaustion incident. Falls back
            # to the default sync engine if the sub-pool isn't wired
            # (worker/scripts don't initialize it in all environments).
            from utils.services.database import ErrorLogSessionLocal

            if ErrorLogSessionLocal is not None:
                database = Database(db=ErrorLogSessionLocal())
            else:
                database = Database()
            try:
                error_log = ErrorLog(
                    error_type=type(error).__name__,
                    error_message=str(error)[:4000],
                    stack_trace=stack_trace,
                    method=method,
                    path=path,
                    status_code=500,
                    user_id=user_id,
                    service="api",
                    request_id=request_id,
                )
                database.create(error_log)
            finally:
                database.close()
        except Exception:
            logger.exception("Failed to log error to error_logs table")

    def execute(self, *args, **kwargs):
        """Executes the business logic of the endpoint."""
        raise NotImplementedError('Endpoint must implement the execute method.')

    class Response(BaseModel):
        """The Response model for the endpoint."""
        success: bool


class AsyncEndpoint(Endpoint):
    """Async counterpart of Endpoint (aam-3).

    Sync semantics are preserved method-for-method; the only difference
    is that `execute`, `run`, and `call` are async. Subclasses override
    `async def execute(...)` and do their DB work via `await self.db.execute(...)`
    or `await self.database.find_by(...)` (the async `AsyncDatabase`).

    Error-log writes stay on the sync engine — they're rare, tiny, and
    a separate concern from request latency. The writer is dispatched
    via `run_in_threadpool` onto the dedicated `error_log_engine`
    carved off in `utils.services.database` so a pool-exhaustion
    incident on the main sync engine can never starve error logging.

    Example:
        class ExampleAsync(AsyncEndpoint):
            async def execute(self, params):
                user = await self.database.find_by(User, id=params.user_id)
                return success(user)

        @router.post("/")
        async def endpoint(params: Params, db=Depends(get_async_database)):
            return await ExampleAsync.call(params, database=db)
    """

    @classmethod
    async def call(cls, *args, **kwargs):  # type: ignore[override]
        return cls.handle_result(await cls(*args, **kwargs).run())

    async def run(self):  # type: ignore[override]
        args = self.args
        kwargs = self.kwargs

        logger.debug(
            "AsyncEndpoint %s - Args: %s, Kwargs: %s",
            self.__class__.__name__,
            args,
            kwargs,
        )

        try:
            logger.info("Executing endpoint: %s", self.__class__.__name__)
            result = await self.execute(*args, **kwargs)
            if endpoint_result_is_valid(result):
                return result
            raise APIException(
                status_code=500,
                detail=(
                    "Endpoint result not valid. Result: "
                    f"{json.dumps(result, cls=CustomEncoder)}"
                ),
                code=ErrorCode.INVALID_ENDPOINT_RESULT,
            )
        except APIException as e:
            logger.error(
                "AsyncEndpoint %s failed with api error: %s",
                self.__class__.__name__,
                str(e),
                exc_info=True,
            )
            return failure(
                error_code=e.code,
                error_message=e.detail,
                status=e.status_code,
                data={},
                error=e,
            )
        except Exception as e:
            logger.error(
                "AsyncEndpoint %s failed with error: %s",
                self.__class__.__name__,
                str(e),
                exc_info=True,
            )
            await self._log_error_to_db_async(e)
            return failure(
                data={},
                error_message=str(e),
                error=e,
            )

    async def _log_error_to_db_async(self, error: Exception) -> None:
        """Dispatch the sync error-log writer onto the threadpool.

        Keeps the async event loop unblocked while the write happens on
        the dedicated `error_log_engine` sub-pool — see
        `utils.services.database.error_log_engine`. Silently swallows
        any threadpool-side exception so error tracking never breaks
        the response (the sync writer already does the same).
        """
        from fastapi.concurrency import run_in_threadpool

        try:
            await run_in_threadpool(self._log_error_to_db, error)
        except Exception:
            logger.exception("Failed to dispatch error log write to threadpool")

    async def execute(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError(
            "AsyncEndpoint must implement the async execute method."
        )


def ack():
    """Helper function to return a generic successful response."""
    return {"success": True}


def success(
    data: typing.Any = None,
    status: int = 200,
    headers: dict | None = None,
):
    """
    A successful response to the service worker.

    :param data: The data to handle the successful response with.
    :param status: The status code of the response.
    :param headers: Optional HTTP response headers to attach.
    :return: A successful response to send to the service worker.
    """
    result = {
        "success": True,
        "data": data if data is not None else ack(),
        "status": status,
    }
    if headers:
        result["headers"] = headers
    return result


def failure(
    error_code: int = ErrorCode.INTERNAL_ERROR.value,
    error_message: str = None,
    error: Exception = None,
    data: dict = None,
    retry_after: int = None,
    status: int = 500
):
    """
    A failed response to the service worker.

    :param error_code: The error_code with why the request failed.
    :param error_message: The error_message with why the request failed.
    :param data: The data to handle the failed response with.
    :param retry_after: The number of seconds to wait before retrying the request.
    :param status: The status code of the response.
    :return: A failed response to send to the service worker.
    """
    if error_message is None:
        error_message = 'Something went wrong.'
    if data is None:
        data = {}
    if isinstance(retry_after, int):
        data["retry_after"] = str(retry_after)
    return {
        "success": False,
        "data": data,
        "error_code": error_code,
        "error_message": error_message,
        "error": error,
        "status": status,
    }


def endpoint_result_is_valid(result):
    """
    Checks if the return result of an endpoint is valid. We want to make sure
    all endpoints follow this structure.

    :param result: The result of the endpoint.
    :return: True if the result is valid, False otherwise.
    """
    if not isinstance(result, dict):
        logger.error("Endpoint result not a dict. Result: %s", result)
        return False

    if 'success' not in result or not isinstance(result['success'], bool):
        logger.error("Endpoint result does not have success. Result: %s", result)
        return False

    if 'status' not in result or not isinstance(result['status'], int):
        logger.error("Endpoint result does not have status. Result: %s", result)
        return False

    if 'error_code' in result:
        if not isinstance(result['error_code'], int):
            logger.error(
                "Endpoint result does not have a valid error_code (not an int). Result: %s",
                result
            )
            return False
        if not any(result['error_code'] == error_code.value for error_code in ErrorCode):
            logger.error(
                "Endpoint result does not have a valid error_code (not in ErrorCode). Result: %s",
                result
            )
            return False

    if 'error_message' in result and not isinstance(result['error_message'], str):
        logger.error("Endpoint result does not have a valid error_message. Result: %s", result)
        return False

    return True
