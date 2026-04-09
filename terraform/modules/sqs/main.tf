# SQS queues for Celery worker

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

# Dead letter queue
resource "aws_sqs_queue" "celery_dlq" {
  name                      = "${var.project}-${var.environment}-celery-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.project}-celery-dlq"
    Environment = var.environment
    Project     = var.project
  }
}

# Main Celery queue
resource "aws_sqs_queue" "celery" {
  name                       = "${var.project}-${var.environment}-celery"
  visibility_timeout_seconds = 3600   # 1 hour, matches Celery config
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20     # Long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.celery_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Name        = "${var.project}-celery"
    Environment = var.environment
    Project     = var.project
  }
}

# Outputs

output "celery_queue_url" {
  value = aws_sqs_queue.celery.url
}

output "celery_queue_arn" {
  value = aws_sqs_queue.celery.arn
}

output "celery_queue_name" {
  value = aws_sqs_queue.celery.name
}

output "celery_dlq_arn" {
  value = aws_sqs_queue.celery_dlq.arn
}

output "celery_queue_prefix" {
  value       = "${var.project}-${var.environment}-"
  description = "Queue name prefix for CELERY_QUEUE_PREFIX env var"
}
