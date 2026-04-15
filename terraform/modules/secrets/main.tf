# Secrets Manager secrets for ECS services

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

# Auth0 configuration
resource "aws_secretsmanager_secret" "auth0" {
  name        = "${var.project}-auth0-${var.environment}"
  description = "Auth0 configuration for ${var.environment}"

  tags = {
    Name        = "${var.project}-auth0"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_secretsmanager_secret_version" "auth0" {
  secret_id = aws_secretsmanager_secret.auth0.id
  secret_string = jsonencode({
    domain    = "placeholder"
    client_id = "placeholder"
    audience  = "placeholder"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# OpenAI configuration
resource "aws_secretsmanager_secret" "openai" {
  name        = "${var.project}-openai-${var.environment}"
  description = "OpenAI configuration for ${var.environment}"

  tags = {
    Name        = "${var.project}-openai"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_secretsmanager_secret_version" "openai" {
  secret_id = aws_secretsmanager_secret.openai.id
  secret_string = jsonencode({
    api_key = "placeholder"
    model   = "gpt-4o-mini"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Outputs

output "auth0_secret_arn" {
  value = aws_secretsmanager_secret.auth0.arn
}

output "openai_secret_arn" {
  value = aws_secretsmanager_secret.openai.arn
}

output "all_secret_arns" {
  value = [
    aws_secretsmanager_secret.auth0.arn,
    aws_secretsmanager_secret.openai.arn,
  ]
}
