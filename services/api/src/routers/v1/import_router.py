"""Import job endpoints router."""

from api.v1.import_job import (
    ApproveImportItem,
    ArchiveImportItem,
    CancelImportJob,
    DismissAllFailedImports,
    DismissImportItem,
    GetImportItem,
    GetImportItemTelemetry,
    GetImportJob,
    GetImportUploadUrl,
    ListImportItems,
    ListImportJobs,
    RetryImportItem,
    SkipImportItem,
    StartImport,
    UnarchiveImportItem,
    UpdateImportItem,
)
from dependencies import get_current_user, get_database
from fastapi import APIRouter, Depends, Query
from utils.models.user import User
from utils.services.database import Database

import_router = APIRouter(tags=["import"])


@import_router.post("/recipe-books/{book_id}/import")
async def start_import(
    book_id: str,
    params: StartImport.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Start a new recipe import job."""
    return StartImport.call(
        book_id=book_id,
        params=params,
        user=user,
        database=database,
    )


@import_router.post("/imports/upload-url")
async def get_import_upload_url(
    params: GetImportUploadUrl.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Mint a presigned S3 PUT URL for a file-based import."""
    return GetImportUploadUrl.call(
        params=params,
        user=user,
        database=database,
    )


@import_router.get("/import-jobs")
async def list_import_jobs(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(
        False, description="Include archived jobs"
    ),
    archived_only: bool = Query(
        False,
        description=(
            "Return only archived jobs (implies include_archived=true; "
            "400 if include_archived=false is also passed)"
        ),
    ),
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List all import jobs for the current user."""
    return ListImportJobs.call(
        status=status,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        archived_only=archived_only,
        user=user,
        database=database,
    )


@import_router.get("/import-jobs/{job_id}")
async def get_import_job(
    job_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get import job details and status."""
    return GetImportJob.call(
        job_id=job_id,
        user=user,
        database=database,
    )


@import_router.delete("/import-jobs/{job_id}")
async def cancel_import_job(
    job_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Cancel an import job."""
    return CancelImportJob.call(
        job_id=job_id,
        user=user,
        database=database,
    )


@import_router.get("/import-jobs/{job_id}/items")
async def list_import_items(
    job_id: str,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(
        False, description="Include archived items"
    ),
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List import items for a job."""
    return ListImportItems.call(
        job_id=job_id,
        status=status,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        user=user,
        database=database,
    )


@import_router.get("/import-items/{item_id}")
async def get_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Get import item details."""
    return GetImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.get("/import-items/{item_id}/telemetry")
async def get_import_item_telemetry(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Per-stage telemetry for the Flutter caret expansion (irrd-2)."""
    return GetImportItemTelemetry.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.put("/import-items/{item_id}")
async def update_import_item(
    item_id: str,
    params: UpdateImportItem.Params,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Update import item with user edits."""
    return UpdateImportItem.call(
        item_id=item_id,
        params=params,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/approve")
async def approve_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Approve import item and create recipe."""
    return ApproveImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/skip")
async def skip_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Skip import item (don't import this recipe)."""
    return SkipImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/retry")
async def retry_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Retry a failed import item from its last successful stage."""
    return RetryImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/dismiss")
async def dismiss_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Hide a failed import item from the UI. Hard dismiss — no undo."""
    return DismissImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.post("/import-jobs/dismiss-all-failed")
async def dismiss_all_failed_imports(
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Hide all failed import items owned by the current user."""
    return DismissAllFailedImports.call(
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/archive")
async def archive_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Archive an import item. 409 if status is in-progress."""
    return ArchiveImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/unarchive")
async def unarchive_import_item(
    item_id: str,
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """Restore an archived import item to the default feed."""
    return UnarchiveImportItem.call(
        item_id=item_id,
        user=user,
        database=database,
    )
