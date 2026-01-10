"""OCR FastAPI service."""

import io
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

from src.config import settings
from src.model import load_model, run_ocr, unload_model


class OCRResponse(BaseModel):
    """OCR response schema."""

    extracted_markdown: str
    source_filename: str | None = None
    warnings: list[str] = []
    meta: dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - preload model."""
    # Optionally preload model on startup
    # load_model()
    yield
    # Cleanup on shutdown
    unload_model()


app = FastAPI(
    title="Palateful OCR Service",
    description="OCR service using HunyuanOCR for recipe extraction",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "model": settings.model_name}


@app.post("/ocr", response_model=OCRResponse)
async def perform_ocr(file: UploadFile = File(...)):
    """
    Perform OCR on an uploaded image.

    Accepts: JPEG, PNG, HEIC (converted), WebP
    Returns: Extracted markdown text
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/heic"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {allowed_types}",
        )

    warnings = []

    try:
        # Read and convert image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")
            warnings.append(f"Converted image from {image.mode} to RGB")

        # Run OCR
        extracted_text = run_ocr(image)

        return OCRResponse(
            extracted_markdown=extracted_text,
            source_filename=file.filename,
            warnings=warnings,
            meta={
                "model": settings.model_name,
                "runtime": "local",
                "timestamp": datetime.utcnow().isoformat(),
                "image_size": f"{image.width}x{image.height}",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e!s}") from e


@app.post("/ocr/url", response_model=OCRResponse)
async def perform_ocr_from_url(url: str):
    """
    Perform OCR on an image from URL.

    Args:
        url: URL of the image to process
    """
    import httpx

    warnings = []

    try:
        # Fetch image from URL
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()

        # Open image
        image = Image.open(io.BytesIO(response.content))

        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")
            warnings.append(f"Converted image from {image.mode} to RGB")

        # Run OCR
        extracted_text = run_ocr(image)

        return OCRResponse(
            extracted_markdown=extracted_text,
            source_filename=url,
            warnings=warnings,
            meta={
                "model": settings.model_name,
                "runtime": "local",
                "timestamp": datetime.utcnow().isoformat(),
                "image_size": f"{image.width}x{image.height}",
            },
        )

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {e!s}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e!s}") from e


@app.get("/model/load")
async def load_model_endpoint():
    """Explicitly load the model into memory."""
    try:
        load_model()
        return {"status": "loaded", "model": settings.model_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e!s}") from e


@app.get("/model/unload")
async def unload_model_endpoint():
    """Unload the model from memory."""
    unload_model()
    return {"status": "unloaded"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
