# IAM roles for AWS Batch and ECS

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "parser_inputs_bucket_arn" {
  type        = string
  description = "ARN of parser inputs S3 bucket"
}

variable "parser_outputs_bucket_arn" {
  type        = string
  description = "ARN of parser outputs S3 bucket"
}

variable "imports_bucket_arn" {
  type        = string
  description = "ARN of user-imports S3 bucket (presigned uploads)."
}

variable "ecr_repository_arn" {
  type        = string
  description = "ARN of ECR repository"
}

variable "create_ecs_roles" {
  type        = bool
  default     = false
  description = "Create IAM roles for ECS tasks"
}

variable "sqs_queue_arns" {
  type        = list(string)
  default     = []
  description = "ARNs of SQS queues for worker access"
}

variable "secrets_arns" {
  type        = list(string)
  default     = []
  description = "ARNs of Secrets Manager secrets for ECS tasks"
}

variable "ssm_secure_parameter_arns" {
  type        = list(string)
  default     = []
  description = <<-EOT
    ARNs of SSM SecureString parameters ECS tasks pull via
    `valueFrom`. Distinct from `secrets_arns` because the IAM action
    for SSM is `ssm:GetParameters`, not `secretsmanager:GetSecretValue`.
    Introduced by pim-5 (2026-04-21) for REDIS_URL.
  EOT
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

# S3 access policy for job role.
# NOTE: The batch_job role runs the parser (Hunyuan OCR) Batch container,
# which does NOT touch the user-imports bucket — ffmpeg / video_file work
# in `sbf-4` lives in the ECS worker, which gets its S3 grant via the
# api_service policy below. Do not extend this block to cover imports
# unless a Batch job actually needs it.
resource "aws_iam_role_policy" "batch_job_s3" {
  name = "${var.project}-batch-job-s3-${var.environment}"
  role = aws_iam_role.batch_job.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "${var.parser_inputs_bucket_arn}/*",
          "${var.parser_outputs_bucket_arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${var.parser_outputs_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [
          var.parser_inputs_bucket_arn,
          var.parser_outputs_bucket_arn
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

# Supplement the legacy AWSBatchServiceRole managed policy with newer
# EC2 permissions that Batch now requires to launch instances.
resource "aws_iam_role_policy" "batch_service_ec2_supplement" {
  name = "${var.project}-batch-service-ec2-supplement-${var.environment}"
  role = aws_iam_role.batch_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EC2PermissionsForBatch"
        Effect = "Allow"
        Action = [
          "ec2:GetSecurityGroupsForVpc",
          "ec2:CreateLaunchTemplate",
          "ec2:DeleteLaunchTemplate",
          "ec2:DescribeLaunchTemplates",
          "ec2:DescribeLaunchTemplateVersions",
        ]
        Resource = "*"
      }
    ]
  })
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

# API Service Policy (for ECS tasks or local dev with AWS credentials)
# This policy allows the API to interact with S3 and Batch
resource "aws_iam_policy" "api_service" {
  name        = "${var.project}-api-service-${var.environment}"
  description = "Policy for API service to access parser S3 buckets and Batch"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ParserAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.parser_inputs_bucket_arn}/*",
          "${var.parser_outputs_bucket_arn}/*"
        ]
      },
      {
        Sid    = "S3ListBuckets"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [
          var.parser_inputs_bucket_arn,
          var.parser_outputs_bucket_arn
        ]
      },
      {
        Sid    = "BatchSubmitAndDescribe"
        Effect = "Allow"
        Action = [
          "batch:SubmitJob",
          "batch:DescribeJobs",
          "batch:ListJobs"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3ImportsAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "${var.imports_bucket_arn}/*"
      },
      {
        # Presigned PUT includes `x-amz-tagging: unclaimed=true` so
        # orphan uploads get swept by the 24h lifecycle rule. AWS
        # requires s3:PutObjectTagging on the signer for a tag-bearing
        # PUT. Post-success retag (clear `unclaimed`) in sbf-3 reuses
        # the same grant. Scoped via Condition to the one tag key we
        # actually write.
        Sid      = "S3ImportsTagging"
        Effect   = "Allow"
        Action   = ["s3:PutObjectTagging"]
        Resource = "${var.imports_bucket_arn}/*"
        Condition = {
          "ForAllValues:StringEquals" = {
            "s3:RequestObjectTagKeys" = ["unclaimed"]
          }
        }
      },
      {
        Sid      = "S3ImportsListBucket"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = var.imports_bucket_arn
      }
    ]
  })

  tags = {
    Name        = "${var.project}-api-service"
    Environment = var.environment
    Project     = var.project
  }
}

# ─── ECS Roles (conditional) ───

# ECS Task Execution Role — pulls images, writes logs, reads secrets
resource "aws_iam_role" "ecs_execution" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.project}-ecs-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-ecs-execution"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  count      = var.create_ecs_roles ? 1 : 0
  role       = aws_iam_role.ecs_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  count = var.create_ecs_roles && length(var.secrets_arns) > 0 ? 1 : 0
  name  = "${var.project}-ecs-execution-secrets-${var.environment}"
  role  = aws_iam_role.ecs_execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SecretsManagerAccess"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.secrets_arns
      }
    ]
  })
}

# pim-5 (2026-04-21): SSM SecureString access for REDIS_URL. Separate
# policy because `ssm:GetParameters` is distinct from
# `secretsmanager:GetSecretValue`, and kms:Decrypt is needed on the
# account-default KMS key SSM uses for SecureStrings.
resource "aws_iam_role_policy" "ecs_execution_ssm" {
  count = var.create_ecs_roles && length(var.ssm_secure_parameter_arns) > 0 ? 1 : 0
  name  = "${var.project}-ecs-execution-ssm-${var.environment}"
  role  = aws_iam_role.ecs_execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SSMGetParameters"
        Effect   = "Allow"
        Action   = ["ssm:GetParameters"]
        Resource = var.ssm_secure_parameter_arns
      },
      {
        Sid      = "SSMKMSDecrypt"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

data "aws_region" "current" {}

# ECS API Task Role — S3, Batch, SQS send
resource "aws_iam_role" "ecs_api_task" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.project}-ecs-api-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-ecs-api-task"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy_attachment" "ecs_api_task_s3_batch" {
  count      = var.create_ecs_roles ? 1 : 0
  role       = aws_iam_role.ecs_api_task[0].name
  policy_arn = aws_iam_policy.api_service.arn
}

resource "aws_iam_role_policy" "ecs_api_task_sqs" {
  count = var.create_ecs_roles && length(var.sqs_queue_arns) > 0 ? 1 : 0
  name  = "${var.project}-ecs-api-task-sqs-${var.environment}"
  role  = aws_iam_role.ecs_api_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SQSSend"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:GetQueueUrl",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.sqs_queue_arns
      },
      {
        Sid      = "SQSListAndDiscover"
        Effect   = "Allow"
        Action   = ["sqs:ListQueues", "sqs:CreateQueue"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_api_task_ssm" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.project}-ecs-api-task-ssm-${var.environment}"
  role  = aws_iam_role.ecs_api_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SSMForECSExec"
        Effect = "Allow"
        Action = [
          "ssmmessages:CreateControlChannel",
          "ssmmessages:CreateDataChannel",
          "ssmmessages:OpenControlChannel",
          "ssmmessages:OpenDataChannel"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_api_task_cloudwatch_logs" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.project}-ecs-api-task-cloudwatch-logs-${var.environment}"
  role  = aws_iam_role.ecs_api_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsRead"
        Effect = "Allow"
        Action = [
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECS Worker Task Role — full SQS + S3 access
resource "aws_iam_role" "ecs_worker_task" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.project}-ecs-worker-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-ecs-worker-task"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_iam_role_policy" "ecs_worker_task_sqs" {
  count = var.create_ecs_roles && length(var.sqs_queue_arns) > 0 ? 1 : 0
  name  = "${var.project}-ecs-worker-task-sqs-${var.environment}"
  role  = aws_iam_role.ecs_worker_task[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SQSQueueAccess"
        Effect   = "Allow"
        Action   = ["sqs:*"]
        Resource = var.sqs_queue_arns
      },
      {
        Sid      = "SQSListAndDiscover"
        Effect   = "Allow"
        Action   = ["sqs:ListQueues", "sqs:GetQueueUrl", "sqs:CreateQueue"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_worker_task_s3_batch" {
  count      = var.create_ecs_roles ? 1 : 0
  role       = aws_iam_role.ecs_worker_task[0].name
  policy_arn = aws_iam_policy.api_service.arn
}

# ECS Migrator Task Role — minimal (only needs DB access via secrets)
resource "aws_iam_role" "ecs_migrator_task" {
  count = var.create_ecs_roles ? 1 : 0
  name  = "${var.project}-ecs-migrator-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ecs-tasks.amazonaws.com" }
      }
    ]
  })

  tags = {
    Name        = "${var.project}-ecs-migrator-task"
    Environment = var.environment
    Project     = var.project
  }
}

# ─── Outputs ───

output "api_service_policy_arn" {
  value       = aws_iam_policy.api_service.arn
  description = "ARN of IAM policy for API service"
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

output "ecs_execution_role_arn" {
  value = try(aws_iam_role.ecs_execution[0].arn, "")
}

output "ecs_api_task_role_arn" {
  value = try(aws_iam_role.ecs_api_task[0].arn, "")
}

output "ecs_worker_task_role_arn" {
  value = try(aws_iam_role.ecs_worker_task[0].arn, "")
}

output "ecs_migrator_task_role_arn" {
  value = try(aws_iam_role.ecs_migrator_task[0].arn, "")
}
