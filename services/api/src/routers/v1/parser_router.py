"""Parser endpoints router."""

from api.v1.parser import (
    CompleteParserBatch,
    CreateParserBatch,
    GetParserBatch,
    GetParserJob,
    GetUploadUrl,
    ListParserBatches,
    SubmitBatchParserJob,
    SubmitParserJob,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, Query
from utils.models.user import User
from utils.services.database import Database

parser_router = APIRouter(prefix="/parser", tags=["parser"])


@parser_router.post("/upload-url")
def get_upload_url(
    params: GetUploadUrl.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Generate a presigned URL for uploading an image."""
    return GetUploadUrl.call(
        params=params,
        user=user,
        database=database,
    )


@parser_router.post("/jobs")
def submit_parser_job(
    params: SubmitParserJob.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Submit a single-image parser job to AWS Batch."""
    return SubmitParserJob.call(
        params=params,
        user=user,
        database=database,
    )


@parser_router.post("/jobs/batch")
def submit_batch_parser_job(
    params: SubmitBatchParserJob.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Submit a multi-image parser job to AWS Batch."""
    return SubmitBatchParserJob.call(
        params=params,
        user=user,
        database=database,
    )


@parser_router.get("/jobs/{job_id}")
def get_parser_job(
    job_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get parser job status and results."""
    return GetParserJob.call(
        job_id=job_id,
        user=user,
        database=database,
    )


@parser_router.post("/batches")
def create_parser_batch(
    params: CreateParserBatch.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Create a parser batch and submit a single AWS Batch job for all images."""
    return CreateParserBatch.call(
        params=params,
        user=user,
        database=database,
    )


@parser_router.get("/batches")
def list_parser_batches(
    active: bool = Query(False),
    limit: int = Query(20),
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List parser batches for the current user."""
    return ListParserBatches.call(
        active=active,
        limit=limit,
        user=user,
        database=database,
    )


@parser_router.get("/batches/{batch_id}")
def get_parser_batch(
    batch_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get a parser batch with nested job state."""
    return GetParserBatch.call(
        batch_id=batch_id,
        user=user,
        database=database,
    )


@parser_router.post("/batches/{batch_id}/complete")
def complete_parser_batch(
    batch_id: str,
    params: CompleteParserBatch.Params,
    database: Database = Depends(get_database),
):
    """Callback invoked by the parser Batch container when it finishes.

    Unauthenticated by design: the handler re-queries AWS Batch for the
    authoritative job state before mutating anything, so untrusted callers
    cannot force a status transition.
    """
    return CompleteParserBatch.call(
        batch_id=batch_id,
        params=params,
        database=database,
    )
