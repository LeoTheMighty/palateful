# HunyuanOCR Batch Architecture

## Overview

Cost-optimized OCR pipeline using AWS Batch with Spot GPU instances. Designed for **"latency doesn't matter; cost matters"** - scales to zero when idle.

## Architecture Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              OCR Pipeline Flow                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Upload Image          2. Submit Batch Job        3. GPU Processing      │
│  ┌─────────────┐         ┌─────────────────┐        ┌─────────────────┐     │
│  │   Client    │────────▶│   S3 Inputs     │        │  Spot GPU EC2   │     │
│  │  (App/API)  │         │   Bucket        │◀───────│  (g4dn/g5)      │     │
│  └─────────────┘         └─────────────────┘        └────────┬────────┘     │
│         │                                                     │             │
│         │                                                     │             │
│         │  aws batch submit-job                              │             │
│         │  ┌─────────────────────────┐                       │             │
│         └─▶│     AWS Batch Queue     │──────────────────────▶│             │
│            │  (hunyuanocr-queue)     │   Provisions only     │             │
│            └─────────────────────────┘   when job submitted  │             │
│                                                               │             │
│                                                               ▼             │
│  4. Output Written       5. App Reads Results                               │
│  ┌─────────────────┐    ┌─────────────────┐                                 │
│  │   S3 Outputs    │◀───│  Container:     │                                 │
│  │   Bucket        │    │  - Download img │                                 │
│  │   (.json/.md)   │    │  - Run OCR      │                                 │
│  └────────┬────────┘    │  - Upload JSON  │                                 │
│           │             └─────────────────┘                                 │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │   App/Notebook  │  Parse OCR output → Structure recipe                   │
│  │   (downstream)  │                                                        │
│  └─────────────────┘                                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Key Properties

- **Scale-to-zero**: min/desired vCPUs = 0 when idle
- **Spot pricing**: 60-90% cheaper than on-demand
- **Async processing**: Batch is async by nature - no HTTP endpoint needed
- **Separation of concerns**: OCR produces raw text; recipe structuring happens downstream

---

## AWS Resources

### S3 Buckets

| Bucket | Purpose | Settings |
|--------|---------|----------|
| `ocr-inputs` | Recipe images (HEIC/JPG/PNG) | SSE-AES256, private |
| `ocr-outputs` | OCR results (JSON/Markdown) | SSE-AES256, lifecycle expiration (dev) |

### IAM Roles

#### 1. Batch Instance Role
Attached to EC2 instances in compute environment.

```hcl
# Policies to attach:
- AmazonEC2ContainerServiceforEC2Role
- AmazonSSMManagedInstanceCore  # For debugging
- ECR pull permissions
- CloudWatch Logs write
```

#### 2. Job Execution Role
Attached to the container task.

```hcl
# Least-privileged S3 access:
{
  "Effect": "Allow",
  "Action": ["s3:GetObject"],
  "Resource": "arn:aws:s3:::ocr-inputs/*"
},
{
  "Effect": "Allow",
  "Action": ["s3:PutObject"],
  "Resource": "arn:aws:s3:::ocr-outputs/*"
}
```

### Batch Compute Environment

```hcl
resource "aws_batch_compute_environment" "hunyuanocr_spot_gpu" {
  compute_environment_name = "hunyuanocr-spot-gpu"
  type                     = "MANAGED"
  state                    = "ENABLED"

  compute_resources {
    type                = "SPOT"
    allocation_strategy = "SPOT_PRICE_CAPACITY_OPTIMIZED"

    min_vcpus     = 0   # Scale to zero!
    desired_vcpus = 0   # Start at zero
    max_vcpus     = 16  # Tune based on usage

    instance_types = [
      "g4dn.xlarge",  # NVIDIA T4 - good for inference
      "g5.xlarge"     # NVIDIA A10G - faster, often similar price
    ]

    subnets            = var.private_subnet_ids
    security_group_ids = [aws_security_group.batch_ce.id]
    instance_role      = aws_iam_instance_profile.batch_instance.arn
  }
}
```

### Job Queue

```hcl
resource "aws_batch_job_queue" "hunyuanocr_queue" {
  name     = "hunyuanocr-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.hunyuanocr_spot_gpu.arn
  }
}
```

### Job Definition

```hcl
resource "aws_batch_job_definition" "hunyuanocr_job" {
  name = "hunyuanocr-job"
  type = "container"

  container_properties = jsonencode({
    image = "${aws_ecr_repository.hunyuanocr.repository_url}:latest"

    resourceRequirements = [
      { type = "VCPU", value = "4" },
      { type = "MEMORY", value = "16384" },  # 16GB
      { type = "GPU", value = "1" }
    ]

    environment = [
      { name = "MODEL_NAME", value = "tencent/HunyuanOCR" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/aws/batch/hunyuanocr"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ocr"
      }
    }
  })

  retry_strategy {
    attempts = 3  # Handle Spot interruptions
  }
}
```

---

## Container Specification

### Dockerfile

```dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    awscli \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ /app/
WORKDIR /app

# Entry point
CMD ["python", "-m", "run_job"]
```

### requirements.txt

```
torch>=2.0
transformers>=4.35
accelerate
boto3
Pillow
```

### Entry Point (run_job.py)

```python
"""
One-shot OCR job for AWS Batch.
Reads image from S3, runs OCR, uploads results to S3.
"""
import os
import json
import boto3
from datetime import datetime
from transformers import AutoProcessor, AutoModelForVision2Seq
from PIL import Image

def main():
    # 1. Read environment variables
    input_uri = os.environ["INPUT_S3_URI"]
    output_uri = os.environ["OUTPUT_S3_URI"]

    # 2. Download input image
    s3 = boto3.client("s3")
    input_bucket, input_key = parse_s3_uri(input_uri)
    local_input = "/tmp/input.png"
    s3.download_file(input_bucket, input_key, local_input)

    # 3. Run OCR inference
    processor = AutoProcessor.from_pretrained("tencent/HunyuanOCR")
    model = AutoModelForVision2Seq.from_pretrained(
        "tencent/HunyuanOCR",
        torch_dtype=torch.float16,
        device_map="auto"
    )

    image = Image.open(local_input)
    inputs = processor(images=image, return_tensors="pt").to("cuda")

    generated_ids = model.generate(**inputs, max_new_tokens=2048)
    extracted_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # 4. Build output
    output = {
        "source_image": input_uri,
        "extracted_markdown": extracted_text,
        "warnings": [],
        "meta": {
            "model": "tencent/HunyuanOCR",
            "runtime": "batch",
            "timestamp": datetime.utcnow().isoformat()
        }
    }

    # 5. Upload to S3
    output_bucket, output_key = parse_s3_uri(output_uri)
    s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=json.dumps(output, indent=2),
        ContentType="application/json"
    )

    print(f"OCR complete. Output: {output_uri}")

def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse s3://bucket/key into (bucket, key)."""
    parts = uri.replace("s3://", "").split("/", 1)
    return parts[0], parts[1]

if __name__ == "__main__":
    main()
```

---

## Output Contract (v0)

```json
{
  "source_image": "s3://ocr-inputs/grandma/biscuits.png",
  "extracted_markdown": "# Grandma's Biscuits\n\n## Ingredients\n- 2 cups flour\n- 1 tbsp baking powder\n...",
  "warnings": [],
  "meta": {
    "model": "tencent/HunyuanOCR",
    "runtime": "batch",
    "timestamp": "2025-01-08T12:34:56Z"
  }
}
```

**Note:** Keep OCR output "faithful" - don't infer missing ingredients. Recipe structuring happens downstream.

---

## Usage

### 1. Build & Push Container

```bash
# Build
docker build -t hunyuanocr-batch:dev .

# Tag for ECR
docker tag hunyuanocr-batch:dev \
  <account>.dkr.ecr.<region>.amazonaws.com/hunyuanocr:dev

# Push
aws ecr get-login-password --region <region> | \
  docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com

docker push <account>.dkr.ecr.<region>.amazonaws.com/hunyuanocr:dev
```

### 2. Apply Terraform

```bash
cd terraform/environments/dev
terraform init
terraform apply
```

### 3. Submit Job

```bash
aws batch submit-job \
  --job-name hunyuanocr-test-001 \
  --job-queue hunyuanocr-queue \
  --job-definition hunyuanocr-job \
  --container-overrides '{
    "environment": [
      {"name":"INPUT_S3_URI","value":"s3://ocr-inputs/grandma/biscuits.png"},
      {"name":"OUTPUT_S3_URI","value":"s3://ocr-outputs/grandma/biscuits.output.json"}
    ]
  }'
```

### 4. Poll Job Status

```bash
aws batch describe-jobs --jobs <jobId>
```

### 5. Fetch Results

```bash
aws s3 cp s3://ocr-outputs/grandma/biscuits.output.json .
cat biscuits.output.json
```

---

## Cost Optimization

### Why This is Cheapest

| Factor | Optimization |
|--------|--------------|
| Idle cost | $0 - compute env scales to zero |
| Instance pricing | Spot = 60-90% off on-demand |
| Runtime | One-shot jobs, not always-on servers |
| Instance selection | Multiple types improve Spot availability |

### Cost Drivers to Watch

1. **Model downloads**: Downloading weights every job is expensive
   - Mitigation: Bake weights into container image
   - Mitigation: Use larger instances with faster download

2. **Job runtime**: Minimize processing time
   - Resize images before upload
   - Batch multiple images per job (future optimization)

3. **Failed jobs**: Spot interruptions
   - Retry strategy handles this
   - Multiple instance types improve availability

---

## HEIC Handling

**Recommended workflow:**
1. Convert HEIC → PNG/JPG **before** uploading to S3
2. Store normalized file in inputs bucket
3. OCR job only handles PNG/JPG

This keeps the OCR container simple and focused.

---

## Security

- [ ] Keep S3 buckets private (no public access)
- [ ] Job role uses least-privilege S3 permissions
- [ ] Batch compute in private subnets with NAT
- [ ] Enable SSM on instances for debugging (no SSH needed)
- [ ] CloudWatch logs for audit trail

---

## Debugging

### Enable SSM Access

Instance role includes `AmazonSSMManagedInstanceCore`. Connect via:

```bash
aws ssm start-session --target <instance-id>
```

### View Logs

```bash
aws logs tail /aws/batch/hunyuanocr --follow
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Job stuck in RUNNABLE | Check instance type availability in region |
| Container fails to start | Check ECR permissions, image exists |
| S3 access denied | Check job role permissions |
| OOM killed | Increase memory in job definition |

---

## Future Upgrades (Post-v0)

### 1. Recipe Structurer Service
Separate CPU task that:
- Takes OCR artifact
- Produces final recipe JSON schema
- Runs validation/coverage checks

### 2. Evaluation Harness
- Missing line rate
- Ingredient quantity/unit extraction accuracy
- Compare against ground truth

### 3. Artifact Versioning
Store for each recipe:
- Raw image
- Normalized image (PNG)
- OCR text (markdown)
- Structured JSON
- Validator report

### 4. Sync OCR Service (if needed)
ECS-on-EC2 vLLM service for low-latency use cases.
Only if truly needed - much more expensive.

---

## Success Criteria (v0)

- [ ] Can submit Batch job with input S3 URI
- [ ] GPU instance launches only during job execution
- [ ] Instance terminates after job completes
- [ ] OCR artifact written to S3
- [ ] App/notebook can read and parse output

---

## Terraform Module Checklist

```hcl
# Required resources:

# S3
aws_s3_bucket.ocr_inputs
aws_s3_bucket.ocr_outputs

# IAM
aws_iam_role.batch_instance_role
aws_iam_instance_profile.batch_instance
aws_iam_role.batch_job_role

# Batch
aws_batch_compute_environment.hunyuanocr_spot_gpu {
  compute_resources {
    type                = "SPOT"
    min_vcpus           = 0
    desired_vcpus       = 0
    allocation_strategy = "SPOT_PRICE_CAPACITY_OPTIMIZED"
    instance_types      = ["g4dn.xlarge", "g5.xlarge"]
  }
}

aws_batch_job_queue.hunyuanocr_queue
aws_batch_job_definition.hunyuanocr_job {
  resourceRequirements = [GPU = 1]
}

# ECR
aws_ecr_repository.hunyuanocr

# CloudWatch
aws_cloudwatch_log_group.batch_logs
```
