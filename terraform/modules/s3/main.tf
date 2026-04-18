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

# CORS configuration for browser uploads via presigned URLs
resource "aws_s3_bucket_cors_configuration" "parser_inputs" {
  bucket = aws_s3_bucket.parser_inputs.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST"]
    allowed_origins = ["*"] # TODO: Restrict to app domains in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
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

# ─── Imports Bucket (presigned user uploads for share extensions) ───
# Receives PDFs, photos, audio, and video uploaded via `/v1/imports/upload-url`
# (epic-share-backend-foundations). Lifecycle expires everything on a short
# horizon because raw uploads are one-shot — we process them into recipes and
# don't need the originals long-term.

resource "aws_s3_bucket" "imports" {
  bucket = "${var.project}-imports-${var.environment}"

  tags = {
    Name        = "${var.project}-imports"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_s3_bucket_versioning" "imports" {
  bucket = aws_s3_bucket.imports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "imports" {
  bucket = aws_s3_bucket.imports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "imports" {
  bucket = aws_s3_bucket.imports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CORS for presigned PUT. The real callers (iOS URLSession, Android
# HttpClient, the worker's boto3 reads) don't go through CORS at all —
# this rule exists only so a future browser-based upload harness can
# hit the bucket without a separate terraform pass. Wildcard origins
# are safe here because the upload URL is presigned per-request; the
# signature is the access control, not the origin.
resource "aws_s3_bucket_cors_configuration" "imports" {
  bucket = aws_s3_bucket.imports.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}

# Lifecycle — two rules:
#   1. Environment-based expiry: 7d in dev, 30d in prod. Keeps cost bounded.
#   2. 24h expiry on objects tagged `unclaimed=true`. The upload-url endpoint
#      will tag objects with this on presign; the /import endpoint clears the
#      tag on success (sbf-2/sbf-3). Orphan uploads where the client never
#      calls /import get swept within a day instead of waiting 7/30.
#
# Both rules also sweep noncurrent versions (bucket has versioning enabled
# above; without this the tombstoned versions would cost storage until the
# outer 7/30-day rule caught them) and abort stuck multipart uploads after
# a day — a common presigned-multipart cost trap.
resource "aws_s3_bucket_lifecycle_configuration" "imports" {
  bucket = aws_s3_bucket.imports.id

  rule {
    id     = "expire-all-objects"
    status = "Enabled"

    filter {} # Apply to all objects

    expiration {
      days = var.environment == "prod" ? 30 : 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "expire-unclaimed-uploads"
    status = "Enabled"

    filter {
      tag {
        key   = "unclaimed"
        value = "true"
      }
    }

    expiration {
      days = 1
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
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

output "imports_bucket_name" {
  value = aws_s3_bucket.imports.bucket
}

output "imports_bucket_arn" {
  value = aws_s3_bucket.imports.arn
}
