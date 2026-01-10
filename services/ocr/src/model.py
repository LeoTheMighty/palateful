"""OCR model loading and inference."""

import torch
from PIL import Image
from transformers import AutoModelForVision2Seq, AutoProcessor

from src.config import settings

# Global model instance
_model = None
_processor = None


def get_device() -> str:
    """Determine the best available device."""
    if settings.device != "auto":
        return settings.device

    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_torch_dtype():
    """Get torch dtype from settings."""
    dtype_map = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    return dtype_map.get(settings.torch_dtype, torch.float16)


def load_model():
    """Load the OCR model and processor."""
    global _model, _processor

    if _model is not None:
        return _model, _processor

    device = get_device()
    dtype = get_torch_dtype()

    print(f"Loading model {settings.model_name} on {device} with {settings.torch_dtype}...")

    _processor = AutoProcessor.from_pretrained(settings.model_name)

    _model = AutoModelForVision2Seq.from_pretrained(
        settings.model_name,
        torch_dtype=dtype,
        device_map=device if device != "cpu" else None,
    )

    if device == "cpu":
        _model = _model.to(device)

    print(f"Model loaded successfully on {device}")
    return _model, _processor


def run_ocr(image: Image.Image, max_new_tokens: int = 2048) -> str:
    """
    Run OCR on an image and return extracted text.

    Args:
        image: PIL Image to process
        max_new_tokens: Maximum tokens to generate

    Returns:
        Extracted text from the image
    """
    model, processor = load_model()
    device = get_device()

    # Prepare inputs
    inputs = processor(images=image, return_tensors="pt")

    # Move to device
    if device != "cpu":
        inputs = {k: v.to(device) for k, v in inputs.items()}

    # Generate
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )

    # Decode
    extracted_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    return extracted_text


def unload_model():
    """Unload the model to free memory."""
    global _model, _processor
    _model = None
    _processor = None
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
