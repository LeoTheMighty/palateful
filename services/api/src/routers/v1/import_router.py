"""Import job endpoints router."""

from api.v1.import_job import (
    ApproveImportItem,
    CancelImportJob,
    GetImportItem,
    GetImportJob,
    ListImportItems,
    SkipImportItem,
    StartImport,
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
    user: User = Depends(get_current_user),
    database: Database = Depends(get_database),
):
    """List import items for a job."""
    return ListImportItems.call(
        job_id=job_id,
        status=status,
        limit=limit,
        offset=offset,
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
