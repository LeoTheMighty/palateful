"""
OCR batch job for AWS Batch.
Supports single image or batch manifest with multiple images.

Single mode (backwards compatible):
  INPUT_S3_URI=s3://bucket/image.jpg OUTPUT_S3_URI=s3://bucket/result.json

Batch mode:
  BATCH_MANIFEST_URI=s3://bucket/manifest.json
  Manifest format: {"items": [{"input_s3_uri": "...", "output_s3_uri": "..."}, ...]}
"""

import io
import json
import os
import sys
from datetime import datetime, timezone

import boto3
import torch
from PIL import Image
from transformers import AutoProcessor
try:
    from transformers.models.hunyuan_vl import HunYuanVLForConditionalGeneration as ModelClass
except ImportError:
    try:
        from transformers import AutoModelForImageTextToText as ModelClass
    except ImportError:
        from transformers import AutoModelForVision2Seq as ModelClass


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parts = uri.replace("s3://", "").split("/", 1)
    return parts[0], parts[1]


def load_model(model_name: str):
    """Load model and processor once."""
    device = get_device()
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    print(f"Loading model {model_name} on {device} with {dtype}...")

    processor = AutoProcessor.from_pretrained(model_name, use_fast=False, trust_remote_code=True)
    model = ModelClass.from_pretrained(
        model_name,
        dtype=dtype,
        device_map="auto" if device != "cpu" else None,
        attn_implementation="eager",
        trust_remote_code=True,
    )

    if device == "cpu":
        model = model.to(device)

    print("Model loaded successfully")
    return model, processor, device


def run_ocr(model, processor, device, image: Image.Image) -> str:
    """Run OCR on a single image using HunyuanOCR chat template."""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": "Read all the text in this image and output it as plain text only. Do not include any bounding boxes, coordinates, or position data. Just output the readable text content, preserving the logical reading order and paragraph structure."},
            ],
        }
    ]

    prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[prompt], images=[image], padding=True, return_tensors="pt")
    if device != "cpu":
        inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=4096,
            do_sample=False,
        )

    # Strip input tokens from output
    input_len = inputs["input_ids"].shape[1]
    output_ids = generated_ids[:, input_len:]
    return processor.batch_decode(output_ids, skip_special_tokens=True)[0]


def process_single(s3, model, processor, device, model_name, input_uri, output_uri):
    """Process a single image: download, OCR, upload result."""
    print(f"\n--- Processing: {input_uri}")

    # Download
    input_bucket, input_key = parse_s3_uri(input_uri)
    response = s3.get_object(Bucket=input_bucket, Key=input_key)
    image_bytes = response["Body"].read()

    # Open and convert
    warnings = []
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode != "RGB":
        warnings.append(f"Converted image from {image.mode} to RGB")
        image = image.convert("RGB")
    print(f"  Image: {image.width}x{image.height}")

    # OCR
    print("  Running OCR...")
    extracted_text = run_ocr(model, processor, device, image)
    print(f"  Extracted {len(extracted_text)} characters")

    # Build and upload output
    output = {
        "source_image": input_uri,
        "extracted_markdown": extracted_text,
        "warnings": warnings,
        "meta": {
            "model": model_name,
            "runtime": "batch",
            "device": device,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "image_size": f"{image.width}x{image.height}",
        },
    }

    output_bucket, output_key = parse_s3_uri(output_uri)
    s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=json.dumps(output, indent=2),
        ContentType="application/json",
    )
    print(f"  Result uploaded to {output_uri}")
    return True


def main():
    model_name = os.environ.get("MODEL_NAME", "tencent/HunyuanOCR")
    input_uri = os.environ.get("INPUT_S3_URI")
    output_uri = os.environ.get("OUTPUT_S3_URI")
    manifest_uri = os.environ.get("BATCH_MANIFEST_URI")

    s3 = boto3.client("s3")

    # Determine items to process
    if manifest_uri:
        # Batch mode: read manifest
        print(f"Batch mode: loading manifest from {manifest_uri}")
        manifest_bucket, manifest_key = parse_s3_uri(manifest_uri)
        response = s3.get_object(Bucket=manifest_bucket, Key=manifest_key)
        manifest = json.loads(response["Body"].read().decode("utf-8"))
        items = manifest["items"]
        print(f"Found {len(items)} items to process")
    elif input_uri and output_uri:
        # Single mode (backwards compatible)
        items = [{"input_s3_uri": input_uri, "output_s3_uri": output_uri}]
    else:
        print("ERROR: Set INPUT_S3_URI+OUTPUT_S3_URI or BATCH_MANIFEST_URI")
        sys.exit(1)

    # Load model once
    model, processor, device = load_model(model_name)

    # Process all items
    succeeded = 0
    failed = 0
    for i, item in enumerate(items):
        print(f"\n[{i + 1}/{len(items)}]")
        try:
            process_single(
                s3, model, processor, device, model_name,
                item["input_s3_uri"], item["output_s3_uri"],
            )
            succeeded += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1
            # Write error output so the caller knows what happened
            try:
                error_output = {
                    "source_image": item["input_s3_uri"],
                    "error": str(e),
                    "meta": {
                        "model": model_name,
                        "runtime": "batch",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                }
                out_bucket, out_key = parse_s3_uri(item["output_s3_uri"])
                s3.put_object(
                    Bucket=out_bucket,
                    Key=out_key,
                    Body=json.dumps(error_output, indent=2),
                    ContentType="application/json",
                )
            except Exception:
                pass

    print(f"\n{'=' * 50}")
    print(f"Done. {succeeded} succeeded, {failed} failed out of {len(items)} items.")

    if failed > 0 and succeeded == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
