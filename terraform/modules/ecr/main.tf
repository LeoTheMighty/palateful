# ECR Repository for OCR container

variable "environment" {
  type        = string
  description = "Environment name (dev, prod)"
}

variable "project" {
  type        = string
  default     = "palateful"
  description = "Project name"
}

resource "aws_ecr_repository" "ocr" {
  name                 = "${var.project}-ocr"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = "${var.project}-ocr"
    Environment = var.environment
    Project     = var.project
  }
}

# Lifecycle policy to keep only recent images
resource "aws_ecr_lifecycle_policy" "ocr" {
  repository = aws_ecr_repository.ocr.name

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
  value = aws_ecr_repository.ocr.repository_url
}

output "repository_arn" {
  value = aws_ecr_repository.ocr.arn
}

output "repository_name" {
  value = aws_ecr_repository.ocr.name
}
