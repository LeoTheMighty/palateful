import asyncio
import logging
import json
import math
import random
from typing import Optional
from celery import Task, group
from celery.worker import strategy
from celery.app import trace

from utils.api.endpoint import endpoint_result_is_valid, failure, APIException
from utils.classes.error_code import ErrorCode
from utils.constants import (
    EXPONENTIAL_BACKOFF_FACTOR,
    LOGGING_LEVEL,
    MIN_BATCH_SIZE,
    MAX_BATCH_SIZE,
    MAX_TASK_COUNTDOWN,
)
from utils.services.database import Database

# We want to set internal celery log level to warning
strategy.logger.setLevel(logging.WARNING)
# We want to set the Task result log level to warning as well because we don't care about task
trace.logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)


# pylint: disable=too-many-instance-attributes,abstract-method
class BaseTask(Task):
    """
    The Base Task for all asynchronous endpoints to be run as celery tasks.

    In order to use this class, inherit from it and implement the
    `execute` methods.

    Note:
        Remember to register each task with `TaskName = celery_app.register_task(TaskName())``.

    """

    args = None
    kwargs = None
    api_request = None
    user_id = None
    base_data = None
    service = None
    stream_client = None
    database = None
    token = None
    catalyst_id = None
    countdown = None

    def on_success(self, retval, task_id, args, kwargs):
        """Takes the return value of the task and responds."""
        logger.info("Task %s executed successfully with task id %s", self.name, task_id)
        if self.database:
            self.database.close()

    # pylint: disable=too-many-arguments
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Takes the failure value of the task and responds."""
        logger.error("Task %s failed with error: %s", self.name, str(exc), exc_info=True)

        error_code = ErrorCode.INTERNAL_ERROR.value
        error_string = str(exc)
        status_code = 500
        if isinstance(exc, APIException):
            error_code = exc.code
            error_string = exc.detail
            status_code = exc.status_code

        if self.stream_client:
            self.stream_client.send_error_message(error_code, error_string, status_code)

        if self.database:
            self.database.close()

    def run(self, *args, **kwargs):
        """
        Runs the celery task.

        Special Keyword Arguments for all tasks:
            stream_channel: The channel to use for streaming
            auth_token: The authentication token to use for streaming

        The rest are passed into the `execute` method of the subclass.

        Arguments:
            args: The positional arguments for the task
            kwargs: The keyword arguments for the task
        """

        self.args = args
        self.kwargs = kwargs.copy()  # Clone the dictionary to avoid side effects

        stream_channel = None
        self.user_id = kwargs.pop('user_id', None)
        self.token = kwargs.pop('auth_token', None)
        self.base_data = kwargs.pop('base_data', None)
        self.countdown = kwargs.pop('countdown', 0.0)

        # if stream_channel and self.token:
        #     self.stream_client = AppSyncClient(stream_channel, auth_token=self.token)

        # Give each task a database connection
        self.database = Database()

        logger.info("Executing task: %s", self.name)
        try:
            result = self.execute(*args, **kwargs)
            if endpoint_result_is_valid(result):
                result['data'] = {**(self.base_data or {}), **result['data']}
                return result
            raise APIException(
                status_code=500,
                detail=f"Endpoint result not valid. Result: {json.dumps(result)}",
                code=ErrorCode.INVALID_ENDPOINT_RESULT
            )
        except Exception as e:
            raise e

    # Child tasks must implement either `execute` or `execute_async`
    def execute(self, *args, **kwargs): # pragma: no cover
        """The specific business logic for the task. Each Task must implement it."""
        # If the both the execute and execute_async methods are not implemented,
        # this will still raise the NotImplementedError.
        return asyncio.run(self.execute_async(*args, **kwargs))

    async def execute_async(self, *args, **kwargs): # pragma: no cover
        """The specific business logic for the task. Child classes may optionally override this."""
        raise NotImplementedError(
            'Tasks must implement either the execute() or execute_async() method.'
        )

    def get_child_task_context(self, **kwargs) -> dict:
        """
        Returns the full context needed for child tasks, allowing for field overrides.

        Arguments:
            kwargs: The keyword arguments for the task

        Returns:
            dict: Context for child task
        """
        stream_channel = kwargs.pop('stream_channel', None)
        context = {
            'base_data': self.base_data,
            'auth_token': self.token,
        }

        return context

    def retry(self, *override_args, **override_kwargs):
        """
        Retries the task with the given arguments.
        """
        kwargs = self.kwargs.copy()
        kwargs.update(override_kwargs)

        countdown = self._exponential_backoff(self.countdown)
        if countdown < 0:
            return False

        logger.info("Retrying task %s after %d countdown seconds", self.name, countdown)

        kwargs['countdown'] = countdown
        self.s(*override_args, **kwargs).apply_async(countdown=math.ceil(countdown))

        return True

    @classmethod
    def _exponential_backoff(cls, last_countdown: float) -> float:
        """
        Returns the countdown for the given attempt.
        """
        if last_countdown == -1:
            return -1

        if last_countdown == 0:
            return EXPONENTIAL_BACKOFF_FACTOR

        countdown = cls._countdown_jitter(last_countdown * EXPONENTIAL_BACKOFF_FACTOR)
        if countdown > MAX_TASK_COUNTDOWN:
            return -1

        return countdown

    @classmethod
    def _countdown_jitter(cls, countdown: float) -> float:
        """
        Returns the countdown for the given attempt.
        """
        return countdown * random.uniform(0.9, 1.1)

    def parallelize(
        self,
        parallelized_args_list,
        *args,
        chunk_arg_name: Optional[str] = None,
        **kwargs
    ):
        """
        Utility helper to fan-out Celery tasks.

        Args:
            parallelized_args_list (Sequence[Any]):
                The iterable whose items should be split into smaller chunks.
            chunk_arg_name (str | None):
                If provided, the *chunk* will be passed as a named keyword
                argument with this key instead of the first positional arg.
            *args / **kwargs:
                Additional positional / keyword arguments that will be
                forwarded *unchanged* to every spawned task.

        Returns:
            celery.result.AsyncResult | None:  The async result of the single
            task/group or ``None`` when *parallelized_args_list* is empty.
        """

        chunks = list(self._chunks(parallelized_args_list))
        logger.info("Executing %s instances of %s", len(chunks), self.__class__.__name__)

        # Nothing to do – short-circuit.
        if not chunks:
            return None

        # Helper to build either positional or keyword signatures.
        def _build_sig(chunk):
            if chunk_arg_name:
                return self.s(*args, **{chunk_arg_name: chunk}, **kwargs)
            return self.s(chunk, *args, **kwargs)

        # Only one chunk → avoid the group overhead and call delay directly.
        if len(chunks) == 1:
            if chunk_arg_name:
                return self.delay(*args, **{chunk_arg_name: chunks[0]}, **kwargs)
            return self.delay(chunks[0], *args, **kwargs)

        # Multiple chunks → spawn a group so they run in parallel.
        sigs = [_build_sig(chunk) for chunk in chunks]
        return group(sigs).apply_async()

    def _chunks(self, seq, *, min_size=MIN_BATCH_SIZE, max_size=MAX_BATCH_SIZE):
        """Generate chunks with a size between *min_size* and *max_size*.

        The algorithm respects the *max_size* ceiling but also ensures that
        the *last* chunk is never smaller than *min_size* by merging it with
        the previous one when necessary.
        """

        if not seq:
            return  # Nothing to yield

        seq = list(seq)
        n = len(seq)

        # When the whole sequence already fits into a single chunk
        if n <= max_size:
            yield seq
            return

        # Compute an initial chunk size that spreads the load as evenly as
        # possible while not exceeding *max_size*.
        num_chunks = math.ceil(n / max_size)
        size = max(min_size, math.ceil(n / num_chunks))

        chunks: list[list] = [seq[i : i + size] for i in range(0, n, size)]

        # Merge a too-small tail chunk into the previous one.
        if len(chunks) > 1 and len(chunks[-1]) < min_size:
            chunks[-2].extend(chunks[-1])
            chunks.pop()

        yield from chunks
