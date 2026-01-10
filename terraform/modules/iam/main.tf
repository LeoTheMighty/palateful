# IAM roles for AWS Batch OCR pipeline

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "ocr_inputs_bucket_arn" {
  type        = string
  description = "ARN of OCR inputs S3 bucket"
}

variable "ocr_outputs_bucket_arn" {
  type        = string
  description = "ARN of OCR outputs S3 bucket"
}

variable "ecr_repository_arn" {
  type        = string
  description = "ARN of ECR repository"
}

# Batch Instance Role (for EC2 instances in compute environment)
resource "aws_iam_role" "batch_instance" {
  name = "${var.project}-batch-instance-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-batch-instance"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "batch_instance_ecs" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "batch_instance_ssm" {
  role       = aws_iam_role.batch_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "batch_instance" {
  name = "${var.project}-batch-instance-${var.environment}"
  role = aws_iam_role.batch_instance.name
}

# Batch Job Role (for containers running in Batch)
resource "aws_iam_role" "batch_job" {
  name = "${var.project}-batch-job-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-batch-job"
    Environment = var.environment
    Project     = var.project
  }
}

# S3 access policy for job role
resource "aws_iam_role_policy" "batch_job_s3" {
  name = "${var.project}-batch-job-s3-${var.environment}"
  role = aws_iam_role.batch_job.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = "${var.ocr_inputs_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = "${var.ocr_outputs_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [
          var.ocr_inputs_bucket_arn,
          var.ocr_outputs_bucket_arn
        ]
      }
    ]
  })
}

# Batch Service Role
resource "aws_iam_role" "batch_service" {
  name = "${var.project}-batch-service-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "batch.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-batch-service"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "batch_service" {
  role       = aws_iam_role.batch_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# Spot Fleet Role
resource "aws_iam_role" "spot_fleet" {
  name = "${var.project}-spot-fleet-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "spotfleet.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-spot-fleet"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "spot_fleet" {
  role       = aws_iam_role.spot_fleet.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole"
}

output "batch_instance_profile_arn" {
  value = aws_iam_instance_profile.batch_instance.arn
}

output "batch_job_role_arn" {
  value = aws_iam_role.batch_job.arn
}

output "batch_service_role_arn" {
  value = aws_iam_role.batch_service.arn
}

output "spot_fleet_role_arn" {
  value = aws_iam_role.spot_fleet.arn
}
