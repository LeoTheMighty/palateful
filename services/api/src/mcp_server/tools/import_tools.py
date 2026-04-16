"""Import & OCR MCP tools.

Imports are async: `import_recipe` returns a job_id immediately and the client
polls `get_import_status` until items show up. Never block the tool call on
parsing — Claude should tell the user "I kicked it off" and keep moving.
"""

from __future__ import annotations

import json

from api.v1.import_job.approve_import_item import ApproveImportItem
from api.v1.import_job.get_import_job import GetImportJob
from api.v1.import_job.list_import_items import ListImportItems
from api.v1.import_job.start_import import StartImport
from fastapi.encoders import jsonable_encoder
from mcp_server.auth import get_current_database, get_current_user
from mcp_server.server import call_endpoint, mcp

_SUPPORTED_SOURCE_TYPES = {"url", "text", "photo"}


def _build_start_import_params(
    source_type: str,
    *,
    url: str | None,
    text: str | None,
    ocr_texts: list[str] | None,
    additional_context: str | None,
) -> StartImport.Params:
    """Translate MCP-shaped args into StartImport.Params with validation."""
    if source_type not in _SUPPORTED_SOURCE_TYPES:
        raise ValueError(
            f"Unsupported source_type '{source_type}'. Expected one of: "
            + ", ".join(sorted(_SUPPORTED_SOURCE_TYPES))
        )

    if source_type == "url":
        if not url or not url.strip():
            raise ValueError("`url` is required when source_type is 'url'")
        return StartImport.Params(source_type="url", url=url.strip())

    if source_type == "text":
        if not text or not text.strip():
            raise ValueError("`text` is required when source_type is 'text'")
        body = text.strip()
        if additional_context and additional_context.strip():
            body = f"{body}\n\nAdditional context: {additional_context.strip()}"
        return StartImport.Params(source_type="text", raw_text=body)

    # source_type == "photo"
    if not ocr_texts or not any((t or "").strip() for t in ocr_texts):
        raise ValueError(
            "`ocr_texts` is required when source_type is 'photo' — pre-extract text "
            "from the image and pass the snippets here"
        )
    cleaned = [t.strip() for t in ocr_texts if t and t.strip()]
    return StartImport.Params(source_type="photo", ocr_texts=cleaned)


def _require_default_book(user) -> str:
    book_id = getattr(user, "default_recipe_book_id", None)
    if not book_id:
        raise ValueError(
            "No book_id provided and user has no default recipe book — "
            "ask which book to import into"
        )
    return str(book_id)


@mcp.tool()
def import_recipe(
    source_type: str,
    url: str | None = None,
    text: str | None = None,
    ocr_texts: list[str] | None = None,
    additional_context: str | None = None,
    book_id: str | None = None,
) -> str:
    """Start importing a recipe from a URL, pasted text, or pre-OCR'd photo.

    This kicks off the import pipeline and returns a `job_id` immediately —
    **do not block the conversation** waiting for it. Poll `get_import_status`
    to check progress. When items reach `awaiting_review`, call
    `approve_import` to finalize each one.

    `source_type` must be one of:
    - "url": pass `url` — scraper + LLM extract run server-side
    - "text": pass `text` — ideal path when you've read a recipe from an
      image yourself; optional `additional_context` is appended to enrich the
      LLM extraction (e.g., "from a Thai cookbook, serves 4")
    - "photo": pass `ocr_texts` — a list of already-extracted text chunks
      per image; the server runs LLM structuring on them

    `book_id` defaults to the user's default recipe book.
    """
    user = get_current_user()
    resolved_book_id = book_id or _require_default_book(user)
    params = _build_start_import_params(
        source_type,
        url=url,
        text=text,
        ocr_texts=ocr_texts,
        additional_context=additional_context,
    )
    return call_endpoint(StartImport, book_id=resolved_book_id, params=params)


@mcp.tool()
def get_import_status(job_id: str, item_limit: int = 20) -> str:
    """Check the status of an in-flight import: job-level counters plus the
    per-item breakdown (name, status, error if failed).

    Poll this after `import_recipe`. When items show `awaiting_review`, they
    need explicit approval via `approve_import`. When the job is `complete`
    with no pending items, you're done.
    """
    user = get_current_user()
    database = get_current_database()

    job_result = GetImportJob(database=database, user=user).run(job_id=job_id)
    if not job_result["success"]:
        return f"Error: {job_result.get('error_message') or 'Unknown error'}"

    items_result = ListImportItems(database=database, user=user).run(
        job_id=job_id, limit=item_limit, offset=0
    )
    if not items_result["success"]:
        return f"Error: {items_result.get('error_message') or 'Unknown error'}"

    combined = {
        "job": jsonable_encoder(job_result["data"]),
        "items": jsonable_encoder(items_result["data"]),
    }
    return json.dumps(combined, default=str)


@mcp.tool()
def approve_import(item_id: str) -> str:
    """Approve a single pending import item, triggering recipe creation.

    Use this after `get_import_status` shows an item in `awaiting_review`.
    The recipe is created in the job's target book.
    """
    return call_endpoint(ApproveImportItem, item_id=item_id)
