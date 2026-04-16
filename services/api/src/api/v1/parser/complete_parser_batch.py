"""Callback endpoint invoked by the parser Batch container when it finishes.

This is the primary completion path — the polling watcher is only a safety net.

No shared-secret auth: the endpoint is unauthenticated but safe because it
re-queries AWS Batch as the source of truth before mutating any state. A caller
cannot cause a status transition unless AWS Batch itself already reports the
job as SUCCEEDED/FAILED. Idempotent: calling twice for the same batch is a
no-op on the second call.
"""

from config import settings
from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.parser_batch import ParserBatch
from utils.services.aws import AWSService
from utils.services.parser_batch_completion import complete_parser_batch


class CompleteParserBatch(Endpoint):
    """Handle parser-batch-completion callback from the Batch container."""

    def execute(self, batch_id: str, params: "CompleteParserBatch.Params"):
        parser_batch = (
            self.database.db.query(ParserBatch)
            .filter(ParserBatch.id == batch_id)
            .first()
        )
        if not parser_batch:
            raise APIException(
                status_code=404,
                detail=f"Parser batch {batch_id} not found",
                code=ErrorCode.NOT_FOUND,
            )

        aws = AWSService(
            region=settings.aws_region,
            parser_inputs_bucket=settings.parser_inputs_bucket,
            parser_outputs_bucket=settings.parser_outputs_bucket,
            batch_job_queue=settings.batch_job_queue,
            batch_job_definition=settings.batch_job_definition,
        )

        final_status = complete_parser_batch(self.database, aws, parser_batch)

        return success(
            data=CompleteParserBatch.Response(
                id=str(parser_batch.id),
                status=final_status,
            )
        )

    class Params(BaseModel):
        # Reserved for future caller-provided context (e.g. succeeded/failed
        # counts). The server does not trust these values — state is always
        # verified against AWS Batch. Making this optional avoids a 422 when
        # the container posts an empty body.
        succeeded: int | None = None
        failed: int | None = None

    class Response(BaseModel):
        id: str
        status: str
