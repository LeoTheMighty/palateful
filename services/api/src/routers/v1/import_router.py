"""Import job endpoints router.

aam-18: handlers flipped to ``async def`` + ``get_async_database`` +
``get_current_user_async``. Every endpoint dispatches through
``await Foo.call(...)`` on an ``AsyncEndpoint`` subclass.

ifh-1: every handler now accepts ``request: Request`` and forwards it
into the endpoint via ``request=request``. Without this, the endpoint
base class's ``self.request`` is ``None`` and the audit writer
(``_log_api_error_to_db``) drops ``request_id`` — leaving every
``error_logs`` row from the import path with a null correlation handle
and forcing triage to fall back to ``user_id + path`` queries. See the
2026-05-03 ``/audit`` handoff.
"""

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
    ImportSeeAllCount,
    ListImportItems,
    ListImportItemsBatch,
    ListImportJobs,
    ListSeeAllImportItems,
    RetryImportItem,
    SkipImportItem,
    StartImport,
    SubmitCorrection,
    UnarchiveImportItem,
    UpdateImportItem,
)
from dependencies import get_async_database, get_current_user_async
from fastapi import APIRouter, Depends, Query, Request
from utils.models.user import User
from utils.services.async_database import AsyncDatabase

import_router = APIRouter(tags=["import"])


@import_router.post("/recipe-books/{book_id}/import")
async def start_import(
    book_id: str,
    params: StartImport.Params,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Start a new recipe import job."""
    return await StartImport.call(
        book_id=book_id,
        params=params,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/imports/upload-url")
async def get_import_upload_url(
    params: GetImportUploadUrl.Params,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Mint a presigned S3 PUT URL for a file-based import."""
    return await GetImportUploadUrl.call(
        params=params,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-jobs")
async def list_import_jobs(
    request: Request,
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
    cursor: str | None = Query(
        None,
        description=(
            "Opaque cursor from a prior page's next_cursor (afh-1b). "
            "Mutually exclusive with offset — both-present returns 400."
        ),
    ),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List all import jobs for the current user."""
    return await ListImportJobs.call(
        status=status,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        archived_only=archived_only,
        cursor=cursor,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-jobs/{job_id}")
async def get_import_job(
    job_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get import job details and status."""
    return await GetImportJob.call(
        job_id=job_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.delete("/import-jobs/{job_id}")
async def cancel_import_job(
    job_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Cancel an import job."""
    return await CancelImportJob.call(
        job_id=job_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-jobs/{job_id}/items")
async def list_import_items(
    job_id: str,
    request: Request,
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(
        False, description="Include archived items"
    ),
    cursor: str | None = Query(
        None,
        description=(
            "Opaque cursor from a prior page's next_cursor (afh-1b). "
            "Mutually exclusive with offset — both-present returns 400."
        ),
    ),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """List import items for a job."""
    return await ListImportItems.call(
        job_id=job_id,
        status=status,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        cursor=cursor,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-items")
async def list_import_items_batch(
    request: Request,
    job_ids: str = Query(
        ...,
        description=(
            "Comma-separated list of import-job UUIDs (max 50). "
            "Returns a flat list of items across all accessible jobs; "
            "each item carries its ``job_id`` for client-side grouping."
        ),
    ),
    status: str | None = Query(None, description="Filter by status"),
    include_archived: bool = Query(
        False,
        description=(
            "Include archived items (default off so the main Imports "
            "feed hides archived rows — See-all pagination flips it on)."
        ),
    ),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Batch-list import items across multiple jobs (ffm-2).

    Registered BEFORE ``/import-items/{item_id}`` + ``/see-all-count``
    so FastAPI's literal-path-first matcher routes the base path here
    instead of into the ``item_id`` path param.
    """
    return await ListImportItemsBatch.call(
        job_ids=job_ids,
        status=status,
        include_archived=include_archived,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-items/see-all-count")
async def import_see_all_count(
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Imports See-all triple (archived, read_and_old_completed, total).

    Registered BEFORE ``/import-items/{item_id}`` so FastAPI's
    literal-path-first matcher doesn't route ``see-all-count`` into the
    ``item_id`` path param.
    """
    return await ImportSeeAllCount.call(
        request=request, user=user, database=database
    )


@import_router.get("/import-items/see-all")
async def list_see_all_import_items(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(
        None,
        description=(
            "Opaque cursor from a prior page's next_cursor. Omit for "
            "the first page."
        ),
    ),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Paginated See-all items (same predicate as /see-all-count).

    Registered BEFORE ``/import-items/{item_id}`` so FastAPI's
    literal-path-first matcher routes ``see-all`` here.
    """
    return await ListSeeAllImportItems.call(
        limit=limit,
        cursor=cursor,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-items/{item_id}")
async def get_import_item(
    item_id: str,
    request: Request,
    include: str | None = Query(
        None,
        description=(
            "ffm-10 — optional CSV. Pass ``parsed_recipe`` to include "
            "the heavy parsed-recipe JSON (telemetry viewer uses this)."
            " Omitted by default."
        ),
    ),
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Get import item details."""
    return await GetImportItem.call(
        item_id=item_id,
        include=include,
        request=request,
        user=user,
        database=database,
    )


@import_router.get("/import-items/{item_id}/telemetry")
async def get_import_item_telemetry(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Per-stage telemetry for the Flutter caret expansion (irrd-2)."""
    return await GetImportItemTelemetry.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.put("/import-items/{item_id}")
async def update_import_item(
    item_id: str,
    params: UpdateImportItem.Params,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Update import item with user edits."""
    return await UpdateImportItem.call(
        item_id=item_id,
        params=params,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/approve")
async def approve_import_item(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Approve import item and create recipe."""
    return await ApproveImportItem.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/skip")
async def skip_import_item(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Skip import item (don't import this recipe)."""
    return await SkipImportItem.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/retry")
async def retry_import_item(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Retry a failed import item from its last successful stage."""
    return await RetryImportItem.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/dismiss")
async def dismiss_import_item(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Hide a failed import item from the UI. Hard dismiss — no undo."""
    return await DismissImportItem.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/corrections")
async def submit_import_correction(
    item_id: str,
    params: SubmitCorrection.Params,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """efi-4 — log a user override on an inferred recipe field.

    Side-channel audit endpoint. Writes one ``error_logs`` row
    (``service="audit"``, ``error_type="InferredFieldCorrected"``) and
    returns 204. Does NOT mutate ``parsed_recipe``; the real user edits
    flow through ``approve_import_item`` at save time.
    """
    return await SubmitCorrection.call(
        item_id=item_id,
        params=params,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-jobs/dismiss-all-failed")
async def dismiss_all_failed_imports(
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Hide all failed import items owned by the current user."""
    return await DismissAllFailedImports.call(
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/archive")
async def archive_import_item(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Archive an import item. 409 if status is in-progress."""
    return await ArchiveImportItem.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )


@import_router.post("/import-items/{item_id}/unarchive")
async def unarchive_import_item(
    item_id: str,
    request: Request,
    user: User = Depends(get_current_user_async),
    database: AsyncDatabase = Depends(get_async_database),
):
    """Restore an archived import item to the default feed."""
    return await UnarchiveImportItem.call(
        item_id=item_id,
        request=request,
        user=user,
        database=database,
    )
