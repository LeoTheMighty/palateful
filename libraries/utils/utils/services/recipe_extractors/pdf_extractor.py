"""PDF recipe extractor — text extraction via PyMuPDF with OCR fallback."""

import logging
from enum import Enum

from utils.services.recipe_extractors.base import ExtractionResult
from utils.services.recipe_extractors.text_extractor import extract_recipe_from_text

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
MAX_PAGES = 100
TEXT_THRESHOLD_CHARS_PER_PAGE = 100


class PDFType(str, Enum):
    TEXT = "text"
    SCANNED = "scanned"


def classify_pdf(file_bytes: bytes) -> tuple[PDFType, int]:
    """Classify a PDF as text-based or scanned.

    Returns (pdf_type, page_count).
    """
    import pymupdf

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    page_count = len(doc)

    if page_count == 0:
        doc.close()
        return PDFType.TEXT, 0

    total_chars = 0
    for page in doc:
        total_chars += len(page.get_text())

    doc.close()
    avg_chars = total_chars / page_count if page_count > 0 else 0
    pdf_type = PDFType.TEXT if avg_chars >= TEXT_THRESHOLD_CHARS_PER_PAGE else PDFType.SCANNED
    return pdf_type, page_count


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a text-based PDF using PyMuPDF."""
    import pymupdf

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    pages_text = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages_text.append(f"--- Page {i + 1} ---\n{text}")
    doc.close()
    return "\n\n".join(pages_text)


def extract_pages_as_images(file_bytes: bytes) -> list[bytes]:
    """Render each page of a scanned PDF as a PNG image."""
    import pymupdf

    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    images = []
    for page in doc:
        # Render at 200 DPI for good OCR quality
        pix = page.get_pixmap(dpi=200)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


def detect_recipe_boundaries(text: str) -> list[dict]:
    """Use AI to detect recipe boundaries in multi-recipe PDF text.

    Returns a list of dicts with 'title' and 'text' for each recipe found.
    If only one recipe detected, returns a single entry.
    """
    import json

    from openai import OpenAI

    # If text is short enough to be a single recipe, skip boundary detection
    if len(text) < 3000:
        return [{"title": "Recipe", "text": text}]

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You identify recipe boundaries in text extracted from PDFs. Return JSON.",
            },
            {
                "role": "user",
                "content": (
                    "This text was extracted from a PDF. Identify where each recipe begins and ends. "
                    "Return a JSON array of objects, each with 'title' (recipe name) and 'text' "
                    "(the full text of that recipe including ingredients and instructions). "
                    "If there is only one recipe, return an array with one element.\n\n"
                    f"{text[:16000]}"
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=4000,
    )

    try:
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        recipes = data.get("recipes", data.get("items", [data] if "title" in data else []))
        if isinstance(recipes, list) and recipes:
            return [{"title": r.get("title", "Recipe"), "text": r.get("text", "")} for r in recipes]
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: treat entire text as one recipe
    return [{"title": "Recipe", "text": text}]


def has_recipe_content_in_text(text: str) -> bool:
    """Quick check if text contains recipe indicators."""
    import re

    indicators = re.compile(
        r"\b(recipe|ingredient|tablespoon|teaspoon|tbsp|tsp|cups?|ounces?|oz"
        r"|preheat|bake|simmer|boil|flour|sugar|butter|salt)\b",
        re.IGNORECASE,
    )
    return len(indicators.findall(text)) >= 2


def extract_recipes_from_pdf(
    file_bytes: bytes,
) -> tuple[list[ExtractionResult], int]:
    """Extract recipes from a PDF file.

    Returns (list_of_results, ai_cost_cents_total).
    Each ExtractionResult corresponds to one detected recipe.
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return [ExtractionResult(
            success=False,
            error_message="PDF file is too large (max 50MB)",
            error_code="PDF_TOO_LARGE",
            extractor_used="pdf",
        )], 0

    pdf_type, page_count = classify_pdf(file_bytes)

    if page_count == 0:
        return [ExtractionResult(
            success=False,
            error_message="PDF has no pages",
            error_code="PDF_EMPTY",
            extractor_used="pdf",
        )], 0

    if page_count > MAX_PAGES:
        return [ExtractionResult(
            success=False,
            error_message=f"PDF has too many pages ({page_count}, max {MAX_PAGES})",
            error_code="PDF_TOO_MANY_PAGES",
            extractor_used="pdf",
        )], 0

    if pdf_type == PDFType.TEXT:
        return _extract_from_text_pdf(file_bytes)
    else:
        return _extract_from_scanned_pdf(file_bytes)


def _extract_from_text_pdf(file_bytes: bytes) -> tuple[list[ExtractionResult], int]:
    """Extract from a text-based PDF."""
    text = extract_text_from_pdf(file_bytes)

    if not text.strip():
        return [ExtractionResult(
            success=False,
            error_message="Could not extract text from PDF",
            error_code="PDF_NO_TEXT",
            extractor_used="pdf_text",
        )], 0

    # Circuit breaker: check first few pages for recipe content
    first_pages = "\n".join(text.split("--- Page")[: 4])
    if not has_recipe_content_in_text(first_pages):
        return [ExtractionResult(
            success=False,
            error_message="This doesn't look like a recipe PDF",
            error_code="PDF_NO_RECIPE_CONTENT",
            extractor_used="pdf_text",
        )], 0

    # Detect recipe boundaries
    recipes = detect_recipe_boundaries(text)

    results = []
    total_cost = 0
    for recipe_chunk in recipes:
        result = extract_recipe_from_text(recipe_chunk["text"])
        if result.success and result.recipe and recipe_chunk.get("title") != "Recipe":
            result.recipe.name = result.recipe.name or recipe_chunk["title"]
        result.extractor_used = "pdf_text"
        total_cost += result.ai_cost_cents
        results.append(result)

    return results if results else [ExtractionResult(
        success=False,
        error_message="No recipes found in PDF",
        error_code="PDF_NO_RECIPES",
        extractor_used="pdf_text",
    )], total_cost


def _extract_from_scanned_pdf(file_bytes: bytes) -> tuple[list[ExtractionResult], int]:
    """Extract from a scanned PDF by converting pages to images.

    Each page is treated as a separate potential recipe. The images would
    normally go through the OCR pipeline, but for simplicity we extract
    what text we can and use AI extraction.
    """
    text = extract_text_from_pdf(file_bytes)

    # Even scanned PDFs often have some embedded text
    if text.strip() and has_recipe_content_in_text(text):
        return _extract_from_text_pdf(file_bytes)

    # For truly scanned PDFs, we'd need OCR (HunyuanOCR pipeline)
    # For now, return a result indicating OCR is needed
    return [ExtractionResult(
        success=False,
        error_message="This PDF appears to be scanned. Photo import is recommended for scanned recipe pages.",
        error_code="PDF_NEEDS_OCR",
        extractor_used="pdf_scanned",
    )], 0
