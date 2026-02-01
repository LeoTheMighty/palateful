# S3 buckets for parser pipeline

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

# Parser Input Bucket
resource "aws_s3_bucket" "parser_inputs" {
  bucket = "${var.project}-parser-inputs-${var.environment}"

  tags = {
    Name        = "${var.project}-parser-inputs"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_s3_bucket_versioning" "parser_inputs" {
  bucket = aws_s3_bucket.parser_inputs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "parser_inputs" {
  bucket = aws_s3_bucket.parser_inputs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "parser_inputs" {
  bucket = aws_s3_bucket.parser_inputs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Parser Output Bucket
resource "aws_s3_bucket" "parser_outputs" {
  bucket = "${var.project}-parser-outputs-${var.environment}"

  tags = {
    Name        = "${var.project}-parser-outputs"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_s3_bucket_versioning" "parser_outputs" {
  bucket = aws_s3_bucket.parser_outputs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "parser_outputs" {
  bucket = aws_s3_bucket.parser_outputs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "parser_outputs" {
  bucket = aws_s3_bucket.parser_outputs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule for dev environment (expire after 30 days)
resource "aws_s3_bucket_lifecycle_configuration" "parser_outputs_lifecycle" {
  count  = var.environment == "dev" ? 1 : 0
  bucket = aws_s3_bucket.parser_outputs.id

  rule {
    id     = "expire-dev-outputs"
    status = "Enabled"

    filter {} # Apply to all objects

    expiration {
      days = 30
    }
  }
}

output "parser_inputs_bucket_name" {
  value = aws_s3_bucket.parser_inputs.bucket
}

output "parser_inputs_bucket_arn" {
  value = aws_s3_bucket.parser_inputs.arn
}

output "parser_outputs_bucket_name" {
  value = aws_s3_bucket.parser_outputs.bucket
}

output "parser_outputs_bucket_arn" {
  value = aws_s3_bucket.parser_outputs.arn
}
