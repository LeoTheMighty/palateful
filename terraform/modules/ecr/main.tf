# ECR Repositories

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

variable "additional_repositories" {
  type        = list(string)
  default     = []
  description = "Additional ECR repository names (e.g. api, worker, migrator)"
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

# Additional repositories (api, worker, migrator)
resource "aws_ecr_repository" "additional" {
  for_each             = toset(var.additional_repositories)
  name                 = "${var.project}/${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "${var.project}/${each.value}"
    Environment = var.environment
    Project     = var.project
  }
}

resource "aws_ecr_lifecycle_policy" "additional" {
  for_each   = toset(var.additional_repositories)
  repository = aws_ecr_repository.additional[each.value].name

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

output "additional_repository_urls" {
  value = { for k, v in aws_ecr_repository.additional : k => v.repository_url }
}

output "additional_repository_arns" {
  value = { for k, v in aws_ecr_repository.additional : k => v.arn }
}
