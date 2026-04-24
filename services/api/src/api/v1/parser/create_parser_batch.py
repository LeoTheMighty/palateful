"""Create parser batch endpoint."""

import uuid
from datetime import UTC, datetime

from config import settings
from pydantic import BaseModel, Field
from utils.api.endpoint import APIException, AsyncEndpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.parser_batch import ParserBatch
from utils.models.parser_job import ParserJob
from utils.services.aws import AWSService


class CreateParserBatch(AsyncEndpoint):
    """Create a parser batch and submit a single AWS Batch job for all images."""

    async def execute(self, params: "CreateParserBatch.Params"):
        if not params.items:
            raise APIException(
                status_code=400,
                detail="At least one item is required",
                code=ErrorCode.INVALID_REQUEST,
            )

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        batch_short_id = str(uuid.uuid4())[:8]

        group_count = len({item.group_index for item in params.items})

        parser_batch = ParserBatch(
            user_id=self.user.id,
            recipe_book_id=uuid.UUID(params.recipe_book_id)
            if params.recipe_book_id
            else None,
            status="pending",
            group_count=group_count,
        )
        await self.database.create(parser_batch)

        manifest_items = []
        parser_jobs: list[ParserJob] = []
        for item in params.items:
            unique_id = str(uuid.uuid4())[:8]
            output_s3_key = (
                f"results/{self.user.id}/{timestamp}_{unique_id}.json"
            )
            parser_job = ParserJob(
                user_id=self.user.id,
                status="pending",
                input_s3_key=item.s3_key,
                output_s3_key=output_s3_key,
                recipe_book_id=parser_batch.recipe_book_id,
                parser_batch_id=parser_batch.id,
                group_index=item.group_index,
            )
            self.database.db.add(parser_job)
            parser_jobs.append(parser_job)
            manifest_items.append(
                {"input_s3_key": item.s3_key, "output_s3_key": output_s3_key}
            )

        await self.database.db.commit()
        for pj in parser_jobs:
            await self.database.db.refresh(pj)

        aws = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )
        manifest_s3_key = (
            f"manifests/{self.user.id}/{timestamp}_{batch_short_id}.json"
        )
        job_name = f"parser-batch-{batch_short_id}"

        # Build callback URL so the container can POST on completion. Empty
        # api_base_url (dev / local) means callback-less — the polling watcher
        # takes over as the sole path.
        extra_env: dict[str, str] = {"PARSER_BATCH_ID": str(parser_batch.id)}
        if settings.api_base_url:
            callback_url = (
                f"{settings.api_base_url.rstrip('/')}/parser/batches/"
                f"{parser_batch.id}/complete"
            )
            extra_env["API_CALLBACK_URL"] = callback_url

        batch_job_id = await aws.submit_batch_manifest_job_async(
            job_name=job_name,
            items=manifest_items,
            manifest_s3_key=manifest_s3_key,
            extra_environment=extra_env,
        )

        for pj in parser_jobs:
            pj.batch_job_id = batch_job_id
            pj.status = "submitted"
        parser_batch.status = "submitted"
        await self.database.db.commit()

        from utils.tasks.import_tasks.watch_parser_batch_task import (
            watch_parser_batch_task,
        )

        watch_parser_batch_task.apply_async(
            args=[str(parser_batch.id)],
            kwargs={"user_id": str(self.user.id)},
            countdown=30,
        )

        return success(
            data=CreateParserBatch.Response(
                id=str(parser_batch.id),
                status=parser_batch.status,
                jobs=[
                    CreateParserBatch.JobInfo(
                        id=str(pj.id),
                        input_s3_key=pj.input_s3_key,
                        group_index=pj.group_index,
                    )
                    for pj in parser_jobs
                ],
            ),
            status=201,
        )

    class Item(BaseModel):
        s3_key: str
        group_index: int = 0

    class Params(BaseModel):
        recipe_book_id: str | None = None
        items: list["CreateParserBatch.Item"] = Field(default_factory=list)

    class JobInfo(BaseModel):
        id: str
        input_s3_key: str
        group_index: int

    class Response(BaseModel):
        id: str
        status: str
        jobs: list["CreateParserBatch.JobInfo"]
