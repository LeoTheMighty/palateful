# ECS Fargate cluster, task definitions, and services

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

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for ECS tasks"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for ECS tasks"
}

variable "execution_role_arn" {
  type        = string
  description = "ECS task execution role ARN"
}

variable "api_task_role_arn" {
  type        = string
  description = "IAM role ARN for API task"
}

variable "worker_task_role_arn" {
  type        = string
  description = "IAM role ARN for Worker task"
}

variable "migrator_task_role_arn" {
  type        = string
  description = "IAM role ARN for Migrator task"
}

variable "api_image" {
  type        = string
  description = "Full ECR image URI for API (with tag)"
}

variable "worker_image" {
  type        = string
  description = "Full ECR image URI for Worker (with tag)"
}

variable "migrator_image" {
  type        = string
  description = "Full ECR image URI for Migrator (with tag)"
}

variable "api_target_group_arn" {
  type        = string
  description = "ALB target group ARN for API"
}

variable "db_master_secret_arn" {
  type        = string
  description = "ARN of the RDS-managed Secrets Manager secret containing username/password JSON. DB_PASSWORD is pulled from the 'password' JSON key at task start, which eliminates drift between RDS and a separately-maintained DATABASE_URL secret."
}

variable "db_host" {
  type        = string
  description = "RDS hostname (no port)"
}

variable "db_port" {
  type        = number
  default     = 5432
  description = "RDS port"
}

variable "db_name" {
  type        = string
  description = "PostgreSQL database name"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL username"
}

variable "db_sslmode" {
  type        = string
  default     = "require"
  description = "libpq sslmode. RDS prod parameter group sets rds.force_ssl=1, so this must be 'require' or stronger for the connection to succeed."
}

variable "auth0_secret_arn" {
  type        = string
  description = "Secrets Manager ARN for Auth0 config"
}

variable "openai_secret_arn" {
  type        = string
  description = "Secrets Manager ARN for OpenAI config"
}

variable "celery_queue_prefix" {
  type        = string
  description = "SQS queue name prefix for Celery"
}

variable "parser_inputs_bucket" {
  type        = string
  description = "S3 bucket name for parser inputs"
}

variable "parser_outputs_bucket" {
  type        = string
  description = "S3 bucket name for parser outputs"
}

variable "batch_job_queue" {
  type        = string
  description = "Batch job queue name"
}

variable "batch_job_definition" {
  type        = string
  description = "Batch job definition name"
}

variable "cors_origins" {
  type        = string
  default     = "[\"http://localhost:3000\",\"http://localhost:8080\",\"https://palateful.app\",\"https://www.palateful.app\"]"
  description = "CORS origins JSON array"
}

variable "firebase_secret_arn" {
  type        = string
  default     = ""
  description = "Secrets Manager ARN for Firebase credentials JSON"
}

# ─── Cluster ───

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project}-${var.environment}"
    Environment = var.environment
    Project     = var.project
  }
}

# ─── Log Groups ───

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project}-api-${var.environment}"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project}-worker-${var.environment}"
  retention_in_days = 30

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_cloudwatch_log_group" "migrator" {
  name              = "/ecs/${var.project}-migrator-${var.environment}"
  retention_in_days = 7

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

# ─── API Task Definition ───

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project}-api-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.api_task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "LOGGING_LEVEL", value = "INFO" },
        { name = "CORS_ORIGINS", value = var.cors_origins },
        { name = "PARSER_INPUTS_BUCKET", value = var.parser_inputs_bucket },
        { name = "PARSER_OUTPUTS_BUCKET", value = var.parser_outputs_bucket },
        { name = "BATCH_JOB_QUEUE", value = var.batch_job_queue },
        { name = "BATCH_JOB_DEFINITION", value = var.batch_job_definition },
        { name = "CELERY_BROKER_URL", value = "sqs://" },
        { name = "CELERY_QUEUE_PREFIX", value = var.celery_queue_prefix },
        { name = "OPENAI_MODEL", value = "gpt-4o-mini" },
        { name = "DB_HOST", value = var.db_host },
        { name = "DB_PORT", value = tostring(var.db_port) },
        { name = "DB_NAME", value = var.db_name },
        { name = "DB_USERNAME", value = var.db_username },
        { name = "DB_SSLMODE", value = var.db_sslmode },
      ]

      secrets = [
        { name = "DB_PASSWORD", valueFrom = "${var.db_master_secret_arn}:password::" },
        { name = "AUTH0_DOMAIN", valueFrom = "${var.auth0_secret_arn}:domain::" },
        { name = "AUTH0_CLIENT_ID", valueFrom = "${var.auth0_secret_arn}:client_id::" },
        { name = "AUTH0_AUDIENCE", valueFrom = "${var.auth0_secret_arn}:audience::" },
        { name = "OPENAI_API_KEY", valueFrom = var.openai_secret_arn },
        { name = "FIREBASE_CREDENTIALS_JSON", valueFrom = var.firebase_secret_arn },
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/health')\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

# ─── API Service ───

resource "aws_ecs_service" "api" {
  name                   = "${var.project}-api-${var.environment}"
  cluster                = aws_ecs_cluster.main.id
  task_definition        = aws_ecs_task_definition.api.arn
  desired_count          = 1
  launch_type            = "FARGATE"
  platform_version       = "LATEST"
  enable_execute_command = true

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

# ─── Worker Task Definition ───

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project}-worker-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.worker_task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.worker_image
      essential = true

      command = ["celery", "-A", "main:app", "worker", "--beat", "--concurrency=1", "--loglevel=info"]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "LOGGING_LEVEL", value = "INFO" },
        { name = "CELERY_BROKER_URL", value = "sqs://" },
        { name = "CELERY_QUEUE_PREFIX", value = var.celery_queue_prefix },
        { name = "CELERY_POLLING_INTERVAL", value = "10" },
        { name = "PARSER_INPUTS_BUCKET", value = var.parser_inputs_bucket },
        { name = "PARSER_OUTPUTS_BUCKET", value = var.parser_outputs_bucket },
        { name = "BATCH_JOB_QUEUE", value = var.batch_job_queue },
        { name = "BATCH_JOB_DEFINITION", value = var.batch_job_definition },
        { name = "OPENAI_MODEL", value = "gpt-4o-mini" },
        { name = "DB_HOST", value = var.db_host },
        { name = "DB_PORT", value = tostring(var.db_port) },
        { name = "DB_NAME", value = var.db_name },
        { name = "DB_USERNAME", value = var.db_username },
        { name = "DB_SSLMODE", value = var.db_sslmode },
      ]

      secrets = [
        { name = "DB_PASSWORD", valueFrom = "${var.db_master_secret_arn}:password::" },
        { name = "OPENAI_API_KEY", valueFrom = var.openai_secret_arn },
        { name = "FIREBASE_CREDENTIALS_JSON", valueFrom = var.firebase_secret_arn },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

# ─── Worker Service ───

resource "aws_ecs_service" "worker" {
  name             = "${var.project}-worker-${var.environment}"
  cluster          = aws_ecs_cluster.main.id
  task_definition  = aws_ecs_task_definition.worker.arn
  desired_count    = 1
  launch_type      = "FARGATE"
  platform_version = "LATEST"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = true
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

# ─── Migrator Task Definition (no service — run as one-off task) ───

resource "aws_ecs_task_definition" "migrator" {
  family                   = "${var.project}-migrator-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.migrator_task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "migrator"
      image     = var.migrator_image
      essential = true

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "DB_HOST", value = var.db_host },
        { name = "DB_PORT", value = tostring(var.db_port) },
        { name = "DB_NAME", value = var.db_name },
        { name = "DB_USERNAME", value = var.db_username },
        { name = "DB_SSLMODE", value = var.db_sslmode },
      ]

      secrets = [
        { name = "DB_PASSWORD", valueFrom = "${var.db_master_secret_arn}:password::" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.migrator.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "migrator"
        }
      }
    }
  ])

  tags = {
    Environment = var.environment
    Project     = var.project
  }
}

# ─── Outputs ───

output "cluster_id" {
  value = aws_ecs_cluster.main.id
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}

output "migrator_task_definition_arn" {
  value = aws_ecs_task_definition.migrator.arn
}

output "api_task_definition_arn" {
  value = aws_ecs_task_definition.api.arn
}

output "worker_task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}
