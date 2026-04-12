"""List parser batches endpoint."""

from api.v1.parser.get_parser_batch import _serialize_batch
from pydantic import BaseModel
from sqlalchemy.orm import selectinload
from utils.api.endpoint import Endpoint, success
from utils.models.import_job import ImportJob
from utils.models.parser_batch import ParserBatch

ACTIVE_STATUSES = ("pending", "submitted", "running", "partial")


class ListParserBatches(Endpoint):
    """List parser batches for the current user."""

    def execute(
        self,
        active: bool = False,
        limit: int = 20,
    ):
        limit = max(1, min(limit, 100))

        query = (
            self.database.db.query(ParserBatch)
            .options(selectinload(ParserBatch.parser_jobs))
            .filter(ParserBatch.user_id == self.user.id)
        )
        if active:
            query = query.filter(ParserBatch.status.in_(ACTIVE_STATUSES))

        batches = (
            query.order_by(ParserBatch.created_at.desc()).limit(limit).all()
        )

        # Single round-trip for related ImportJobs
        batch_ids = [b.id for b in batches]
        import_jobs_by_batch: dict = {}
        if batch_ids:
            for ij in (
                self.database.db.query(ImportJob)
                .filter(ImportJob.parser_batch_id.in_(batch_ids))
                .all()
            ):
                import_jobs_by_batch.setdefault(ij.parser_batch_id, []).append(ij)

        return success(
            data=ListParserBatches.Response(
                batches=[
                    _serialize_batch(
                        b, import_jobs_by_batch.get(b.id, [])
                    )
                    for b in batches
                ],
            )
        )

    class Response(BaseModel):
        batches: list[dict]
