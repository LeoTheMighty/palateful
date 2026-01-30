"""Schemas for import job API endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class StartImportRequest(BaseModel):
    """Request schema for starting an import."""

    source_type: str = Field(
        ...,
        description="Type of import source",
        pattern="^(url|url_list|spreadsheet|pdf)$",
    )
    urls: list[str] | None = Field(
        None,
        description="List of URLs to import (for url_list source type)",
    )
    url: str | None = Field(
        None,
        description="Single URL to import (for url source type)",
    )


class ImportJobResponse(BaseModel):
    """Response schema for import job."""

    id: str
    status: str
    source_type: str
    source_filename: str | None = None
    total_items: int = 0
    processed_items: int = 0
    succeeded_items: int = 0
    failed_items: int = 0
    pending_review_items: int = 0
    total_ai_cost_cents: int = 0
    recipe_book_id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ImportItemSummary(BaseModel):
    """Summary of an import item for listing."""

    id: str
    status: str
    source_type: str
    source_url: str | None = None
    recipe_name: str | None = None
    error_message: str | None = None
    needs_review: bool = False
    ai_cost_cents: int = 0
    created_at: datetime


class ImportItemDetail(BaseModel):
    """Detailed import item response."""

    id: str
    status: str
    source_type: str
    source_reference: str | None = None
    source_url: str | None = None
    raw_data: dict = Field(default_factory=dict)
    parsed_recipe: dict | None = None
    user_edits: dict | None = None
    error_message: str | None = None
    error_code: str | None = None
    retry_count: int = 0
    ai_cost_cents: int = 0
    import_job_id: str
    created_recipe_id: str | None = None
    created_at: datetime
    updated_at: datetime


class UpdateImportItemRequest(BaseModel):
    """Request schema for updating an import item."""

    user_edits: dict = Field(
        ...,
        description="User edits to the parsed recipe",
    )


class ImportItemListResponse(BaseModel):
    """Response schema for listing import items."""

    items: list[ImportItemSummary]
    total: int
    has_more: bool


class ParsedIngredient(BaseModel):
    """Parsed ingredient data."""

    text: str
    quantity: float | None = None
    unit: str | None = None
    name: str | None = None
    notes: str | None = None
    is_optional: bool = False
    matched_ingredient_id: str | None = None
    match_confidence: float = 0
    match_type: str | None = None
    needs_review: bool = False


class ParsedRecipe(BaseModel):
    """Parsed recipe data."""

    name: str
    description: str | None = None
    ingredients: list[ParsedIngredient] = Field(default_factory=list)
    instructions: str | None = None
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    image_url: str | None = None
    source_url: str | None = None
    author: str | None = None
    cuisine: str | None = None
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
