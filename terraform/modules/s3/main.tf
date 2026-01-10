# S3 buckets for OCR pipeline

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

# OCR Input Bucket
resource "aws_s3_bucket" "ocr_inputs" {
  bucket = "${var.project}-ocr-inputs-${var.environment}"

  tags = {
    Name        = "${var.project}-ocr-inputs"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_s3_bucket_versioning" "ocr_inputs" {
  bucket = aws_s3_bucket.ocr_inputs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ocr_inputs" {
  bucket = aws_s3_bucket.ocr_inputs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "ocr_inputs" {
  bucket = aws_s3_bucket.ocr_inputs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# OCR Output Bucket
resource "aws_s3_bucket" "ocr_outputs" {
  bucket = "${var.project}-ocr-outputs-${var.environment}"

  tags = {
    Name        = "${var.project}-ocr-outputs"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_s3_bucket_versioning" "ocr_outputs" {
  bucket = aws_s3_bucket.ocr_outputs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ocr_outputs" {
  bucket = aws_s3_bucket.ocr_outputs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "ocr_outputs" {
  bucket = aws_s3_bucket.ocr_outputs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule for dev environment (expire after 30 days)
resource "aws_s3_bucket_lifecycle_configuration" "ocr_outputs_lifecycle" {
  count  = var.environment == "dev" ? 1 : 0
  bucket = aws_s3_bucket.ocr_outputs.id

  rule {
    id     = "expire-dev-outputs"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

output "ocr_inputs_bucket_name" {
  value = aws_s3_bucket.ocr_inputs.bucket
}

output "ocr_inputs_bucket_arn" {
  value = aws_s3_bucket.ocr_inputs.arn
}

output "ocr_outputs_bucket_name" {
  value = aws_s3_bucket.ocr_outputs.bucket
}

output "ocr_outputs_bucket_arn" {
  value = aws_s3_bucket.ocr_outputs.arn
}
