# ECR Repository for parser container

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

resource "aws_ecr_repository" "parser" {
  name                 = "${var.project}-parser"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "${var.project}-parser"
    Environment = var.environment
    Project     = var.project
  }
}

# Lifecycle policy to keep only recent images
resource "aws_ecr_lifecycle_policy" "parser" {
  repository = aws_ecr_repository.parser.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

output "repository_url" {
  value = aws_ecr_repository.parser.repository_url
}

output "repository_arn" {
  value = aws_ecr_repository.parser.arn
}

output "repository_name" {
  value = aws_ecr_repository.parser.name
}
