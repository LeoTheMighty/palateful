"""Get CloudWatch logs endpoint."""

import logging

from config import settings
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from utils.api.endpoint import AsyncEndpoint, success

logger = logging.getLogger(__name__)


class GetLogs(AsyncEndpoint):
    """Proxy to CloudWatch FilterLogEvents."""

    async def execute(
        self,
        service: str = "api",
        level: str | None = None,
        search: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 100,
    ):
        """Fetch logs from CloudWatch for the given service."""
        env = settings.environment if settings.environment != "dev" else "prod"
        log_group = f"/ecs/palateful-{service}-{env}"

        # Build filter pattern
        filter_parts = []
        if level:
            filter_parts.append(f'"{level.upper()}"')
        if search:
            filter_parts.append(f'"{search}"')
        filter_pattern = " ".join(filter_parts) if filter_parts else ""

        try:
            import boto3

            client = boto3.client("logs", region_name=settings.aws_region)

            kwargs: dict = {
                "logGroupName": log_group,
                "limit": min(limit, 500),
                "interleaved": True,
            }
            if filter_pattern:
                kwargs["filterPattern"] = filter_pattern
            if start_time is not None:
                kwargs["startTime"] = start_time
            if end_time is not None:
                kwargs["endTime"] = end_time

            # boto3 is sync; dispatch to the threadpool so the async event
            # loop isn't blocked on the CloudWatch round-trip.
            response = await run_in_threadpool(
                lambda: client.filter_log_events(**kwargs)
            )

            events = [
                GetLogs.LogEvent(
                    timestamp=evt.get("timestamp", 0),
                    message=evt.get("message", ""),
                    log_stream_name=evt.get("logStreamName", ""),
                )
                for evt in response.get("events", [])
            ]

            return success(
                data=GetLogs.Response(
                    events=events,
                    count=len(events),
                    log_group=log_group,
                )
            )

        except Exception as e:
            logger.warning("CloudWatch unavailable: %s", str(e))
            return success(
                data=GetLogs.Response(
                    events=[],
                    count=0,
                    log_group=log_group,
                    error=f"CloudWatch unavailable: {str(e)}",
                )
            )

    class LogEvent(BaseModel):
        """A single log event."""

        timestamp: int
        message: str
        log_stream_name: str

    class Response(BaseModel):
        """Response model."""

        events: list["GetLogs.LogEvent"]
        count: int
        log_group: str
        error: str | None = None
