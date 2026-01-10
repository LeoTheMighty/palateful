"""
One-shot OCR job for AWS Batch.
Reads image from S3, runs OCR, uploads results to S3.
"""

import json
import os
from datetime import datetime, timezone

import boto3
import torch
from PIL import Image
from transformers import AutoModelForVision2Seq, AutoProcessor


def get_device() -> str:
    """Determine the best available device."""
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse s3://bucket/key into (bucket, key)."""
    parts = uri.replace("s3://", "").split("/", 1)
    return parts[0], parts[1]


def main():
    """Main entry point for batch job."""
    # 1. Read environment variables
    input_uri = os.environ.get("INPUT_S3_URI")
    output_uri = os.environ.get("OUTPUT_S3_URI")
    model_name = os.environ.get("MODEL_NAME", "tencent/HunyuanOCR")

    if not input_uri or not output_uri:
        raise ValueError("INPUT_S3_URI and OUTPUT_S3_URI environment variables required")

    print(f"Input: {input_uri}")
    print(f"Output: {output_uri}")
    print(f"Model: {model_name}")

    # 2. Download input image from S3
    s3 = boto3.client("s3")
    input_bucket, input_key = parse_s3_uri(input_uri)
    local_input = "/tmp/input_image"

    print(f"Downloading from s3://{input_bucket}/{input_key}...")
    s3.download_file(input_bucket, input_key, local_input)

    # 3. Load and prepare image
    image = Image.open(local_input)
    if image.mode != "RGB":
        image = image.convert("RGB")
    print(f"Image size: {image.width}x{image.height}")

    # 4. Load model
    device = get_device()
    dtype = torch.float16 if device == "cuda" else torch.float32
    print(f"Loading model on {device} with {dtype}...")

    processor = AutoProcessor.from_pretrained(model_name)
    model = AutoModelForVision2Seq.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map=device if device != "cpu" else None,
    )

    if device == "cpu":
        model = model.to(device)

    print("Model loaded successfully")

    # 5. Run OCR inference
    print("Running OCR...")
    inputs = processor(images=image, return_tensors="pt")
    if device != "cpu":
        inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=2048,
            do_sample=False,
        )

    extracted_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    print(f"Extracted {len(extracted_text)} characters")

    # 6. Build output
    output = {
        "source_image": input_uri,
        "extracted_markdown": extracted_text,
        "warnings": [],
        "meta": {
            "model": model_name,
            "runtime": "batch",
            "device": device,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "image_size": f"{image.width}x{image.height}",
        },
    }

    # 7. Upload to S3
    output_bucket, output_key = parse_s3_uri(output_uri)
    print(f"Uploading to s3://{output_bucket}/{output_key}...")

    s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=json.dumps(output, indent=2),
        ContentType="application/json",
    )

    print(f"OCR complete. Output: {output_uri}")
    print("=" * 50)
    print("Extracted text preview:")
    print(extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text)


if __name__ == "__main__":
    main()
