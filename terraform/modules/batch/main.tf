# AWS Batch compute environment for OCR with Spot GPU instances

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

variable "batch_instance_profile_arn" {
  type        = string
  description = "ARN of Batch instance profile"
}

variable "batch_service_role_arn" {
  type        = string
  description = "ARN of Batch service role"
}

variable "batch_job_role_arn" {
  type        = string
  description = "ARN of Batch job role"
}

variable "spot_fleet_role_arn" {
  type        = string
  description = "ARN of Spot Fleet role"
}

variable "ecr_repository_url" {
  type        = string
  description = "ECR repository URL for OCR container"
}

variable "subnet_ids" {
  type        = list(string)
  description = "List of subnet IDs for compute environment"
}

variable "security_group_ids" {
  type        = list(string)
  description = "List of security group IDs for compute environment"
}

variable "max_vcpus" {
  type        = number
  default     = 16
  description = "Maximum vCPUs for compute environment"
}

# Compute Environment - Spot GPU instances
resource "aws_batch_compute_environment" "ocr_spot_gpu" {
  compute_environment_name = "${var.project}-ocr-spot-gpu-${var.environment}"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = var.batch_service_role_arn

  compute_resources {
    type                = "SPOT"
    allocation_strategy = "SPOT_PRICE_CAPACITY_OPTIMIZED"

    min_vcpus     = 0  # Scale to zero when idle
    desired_vcpus = 0  # Start at zero
    max_vcpus     = var.max_vcpus

    instance_type = [
      "g4dn.xlarge",   # NVIDIA T4 - good for inference, ~$0.16/hr spot
      "g5.xlarge",     # NVIDIA A10G - faster, similar spot price
    ]

    subnets            = var.subnet_ids
    security_group_ids = var.security_group_ids
    instance_role      = var.batch_instance_profile_arn
    spot_iam_fleet_role = var.spot_fleet_role_arn

    tags = {
      Name        = "${var.project}-ocr-batch"
      Environment = var.environment
      Project     = var.project
    }
  }

  tags = {
    Name        = "${var.project}-ocr-compute-env"
    Environment = var.environment
    Project     = var.project
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Job Queue
resource "aws_batch_job_queue" "ocr" {
  name     = "${var.project}-ocr-queue-${var.environment}"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.ocr_spot_gpu.arn
  }

  tags = {
    Name        = "${var.project}-ocr-queue"
    Environment = var.environment
    Project     = var.project
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "ocr_batch" {
  name              = "/aws/batch/${var.project}-ocr-${var.environment}"
  retention_in_days = var.environment == "prod" ? 30 : 7

  tags = {
    Name        = "${var.project}-ocr-logs"
    Environment = var.environment
    Project     = var.project
  }
}

# Job Definition
resource "aws_batch_job_definition" "ocr" {
  name = "${var.project}-ocr-job-${var.environment}"
  type = "container"

  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 3  # Handle Spot interruptions
  }

  timeout {
    attempt_duration_seconds = 1800  # 30 minutes max
  }

  container_properties = jsonencode({
    image = "${var.ecr_repository_url}:latest"

    resourceRequirements = [
      { type = "VCPU", value = "4" },
      { type = "MEMORY", value = "16384" },  # 16GB
      { type = "GPU", value = "1" }
    ]

    jobRoleArn = var.batch_job_role_arn

    environment = [
      { name = "MODEL_NAME", value = "tencent/HunyuanOCR" },
      { name = "DEVICE", value = "cuda" },
      { name = "TORCH_DTYPE", value = "float16" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ocr_batch.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ocr"
      }
    }
  })

  tags = {
    Name        = "${var.project}-ocr-job-def"
    Environment = var.environment
    Project     = var.project
  }
}

output "compute_environment_arn" {
  value = aws_batch_compute_environment.ocr_spot_gpu.arn
}

output "job_queue_arn" {
  value = aws_batch_job_queue.ocr.arn
}

output "job_queue_name" {
  value = aws_batch_job_queue.ocr.name
}

output "job_definition_arn" {
  value = aws_batch_job_definition.ocr.arn
}

output "job_definition_name" {
  value = aws_batch_job_definition.ocr.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.ocr_batch.name
}
