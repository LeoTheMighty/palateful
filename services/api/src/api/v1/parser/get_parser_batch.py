"""Get parser batch endpoint."""

from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from utils.api.endpoint import APIException, Endpoint, success
from utils.classes.error_code import ErrorCode
from utils.models.import_job import ImportJob
from utils.models.parser_batch import ParserBatch


class GetParserBatch(Endpoint):
    """Get a parser batch with nested job + import job state."""

    def execute(self, batch_id: str):
        parser_batch = (
            self.database.db.query(ParserBatch)
            .options(selectinload(ParserBatch.parser_jobs))
            .filter(ParserBatch.id == batch_id)
            .first()
        )
        if not parser_batch:
            raise APIException(
                status_code=404,
                detail=f"Parser batch with ID '{batch_id}' not found",
                code=ErrorCode.NOT_FOUND,
            )

        if parser_batch.user_id != self.user.id:
            raise APIException(
                status_code=403,
                detail="You don't have permission to access this batch",
                code=ErrorCode.FORBIDDEN,
            )

        import_jobs = (
            self.database.db.query(ImportJob)
            .filter(ImportJob.parser_batch_id == parser_batch.id)
            .all()
        )

        return success(data=_serialize_batch(parser_batch, import_jobs))

    class Response(BaseModel):
        id: str
        status: str
        group_count: int
        recipe_book_id: str | None
        created_at: str
        completed_at: str | None
        error_message: str | None
        jobs: list["GetParserBatch.JobInfo"]
        import_jobs: list["GetParserBatch.ImportJobInfo"]

    class JobInfo(BaseModel):
        id: str
        status: str
        input_s3_key: str | None
        group_index: int
        extracted_text: str | None
        error_message: str | None

    class ImportJobInfo(BaseModel):
        id: str
        status: str


def _serialize_batch(parser_batch: ParserBatch, import_jobs: list[ImportJob]) -> dict:
    return {
        "id": str(parser_batch.id),
        "status": parser_batch.status,
        "group_count": parser_batch.group_count,
        "recipe_book_id": str(parser_batch.recipe_book_id)
        if parser_batch.recipe_book_id
        else None,
        "created_at": parser_batch.created_at.isoformat(),
        "completed_at": parser_batch.completed_at.isoformat()
        if parser_batch.completed_at
        else None,
        "error_message": parser_batch.error_message,
        "jobs": [
            {
                "id": str(pj.id),
                "status": pj.status,
                "input_s3_key": pj.input_s3_key,
                "group_index": pj.group_index,
                "extracted_text": pj.extracted_text,
                "error_message": pj.error_message,
            }
            for pj in parser_batch.parser_jobs
        ],
        "import_jobs": [
            {"id": str(ij.id), "status": ij.status} for ij in import_jobs
        ],
    }
