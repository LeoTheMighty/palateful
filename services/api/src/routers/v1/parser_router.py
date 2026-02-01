"""Parser endpoints router."""

from api.v1.parser import GetParserJob, GetUploadUrl, SubmitParserJob
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends
from utils.models.user import User
from utils.services.database import Database

parser_router = APIRouter(prefix="/parser", tags=["parser"])


@parser_router.post("/upload-url")
async def get_upload_url(
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
async def submit_parser_job(
    params: SubmitParserJob.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Submit a parser job to AWS Batch."""
    return SubmitParserJob.call(
        params=params,
        user=user,
        database=database,
    )


@parser_router.get("/jobs/{job_id}")
async def get_parser_job(
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
